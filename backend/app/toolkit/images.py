"""
大頭貼的驗證與編碼。**不需要 Pillow**，也不需要外部儲存服務。

===========================================================================
先講兩個會決定做法的限制
===========================================================================
**一、Render 的磁碟是暫時性的**

你把檔案寫到 `/uploads/avatar.jpg`，服務重新部署或重啟之後**那個檔案就不見了**。
免費方案沒有持久磁碟。所以大頭貼不能存檔案系統。

三個選項：

    存資料庫（bytes 欄位）     免費、簡單、不用額外服務  ← 我們選這個
    外部儲存（S3、Cloudinary） 正確做法，但要註冊、要金鑰、要學 SDK
    Render 持久磁碟            要付費

**大頭貼很小（縮到 256×256 之後大約 20~50 KB）**，存資料庫完全沒問題。
如果是使用者上傳的照片、附件那種大檔案，就不能這樣做。

**二、縮圖在前端做，不在後端**

後端縮圖要裝 Pillow，映像檔會變大、部署變慢。
而瀏覽器的 canvas 本來就會縮圖，**一行 `canvas.toBlob()` 就搞定**。

所以分工是：

    前端  用 canvas 縮到 256×256、轉成 JPEG、再上傳
    後端  驗證它真的是圖片、大小合理，然後存起來

===========================================================================
⚠️ 為什麼不能只看副檔名或 Content-Type
===========================================================================
兩者**都是使用者說了算的**，可以隨便偽造。

有人可以把一個 Python 腳本改名成 `avatar.jpg`，
Content-Type 手動填成 `image/jpeg`，然後上傳。
如果你只看那兩個，就把一個可執行檔存進資料庫了。

正確做法是看**檔案開頭的幾個位元組**（magic bytes）——
那是檔案格式本身的一部分，偽造它就等於真的做出一個合法的圖片檔。
"""

from __future__ import annotations

import base64

__all__ = [
    "InvalidImage",
    "MAX_BYTES",
    "ALLOWED",
    "sniff_type",
    "validate_avatar",
    "to_data_uri",
    "from_data_uri",
]

# 256×256 的 JPEG 大約 20~50 KB。200 KB 已經非常寬鬆了。
#
# ⚠️ 一定要有上限。沒有的話，有人上傳一個 500 MB 的檔案就能
# 把你的記憶體和資料庫吃光——這叫資源耗盡攻擊，防起來只要一個判斷。
MAX_BYTES = 200 * 1024

# 每種格式開頭的識別位元組。
# 這幾個是格式規範的一部分，不是慣例，所以可以拿來判斷。
_MAGIC: list[tuple[bytes, str]] = [
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
]

ALLOWED = ("image/jpeg", "image/png", "image/webp")


class InvalidImage(ValueError):
    """
    圖片不合格時丟出。

    路由接到它應該轉成 **HTTP 422**，並把 `str(exc)` 當訊息回給前端——
    訊息已經是寫給使用者看的中文了。
    """


def sniff_type(data: bytes) -> str | None:
    """
    從檔案開頭判斷它真正的格式。

    參數
        data (bytes): 檔案內容。至少要有前 12 個位元組才判斷得出來。

    回傳
        str | None: MIME 型別，認不出來就回 None。

    範例
        >>> sniff_type(b"\\xff\\xd8\\xff\\xe0" + b"0" * 20)
        'image/jpeg'
        >>> sniff_type(b"import os")            # 這是 Python 檔案
        >>> sniff_type(b"")

    注意
        ⚠️ **不要用副檔名或 Content-Type 判斷**，那兩個使用者可以隨便填。
        這支看的是檔案格式本身的識別位元組。
    """
    if not data:
        return None
    for magic, mime in _MAGIC:
        if data.startswith(magic):
            return mime
    # WebP 的格式是 RIFF....WEBP，中間四個位元組是檔案長度
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def validate_avatar(data: bytes, *, max_bytes: int = MAX_BYTES) -> str:
    """
    驗證一份上傳的大頭貼，回傳它真正的 MIME 型別。

    參數
        data (bytes): 檔案內容。
        max_bytes (int): 大小上限，預設 200 KB。

    回傳
        str: MIME 型別，例如 `"image/jpeg"`。

    丟出
        InvalidImage: 空的、太大、或不是允許的圖片格式。
            訊息是中文的，可以直接回給前端。

    範例
        >>> jpeg = b"\\xff\\xd8\\xff\\xe0" + b"0" * 100
        >>> validate_avatar(jpeg)
        'image/jpeg'
        >>> validate_avatar(b"import os")
        Traceback (most recent call last):
        InvalidImage: 這不是有效的圖片檔（只接受 JPEG、PNG、WebP）
        >>> validate_avatar(b"\\xff\\xd8\\xff" + b"0" * 300000)
        Traceback (most recent call last):
        InvalidImage: 圖片太大了，最多 200 KB，這張是 293 KB

    注意
        **檢查順序是刻意的**：先看大小再看格式。
        反過來的話，一個 500 MB 的假圖片會先被完整讀進記憶體去比對開頭。
    """
    if not data:
        raise InvalidImage("沒有收到檔案內容")
    if len(data) > max_bytes:
        raise InvalidImage(
            f"圖片太大了，最多 {max_bytes // 1024} KB，"
            f"這張是 {len(data) // 1024} KB"
        )
    mime = sniff_type(data)
    if mime not in ALLOWED:
        raise InvalidImage("這不是有效的圖片檔（只接受 JPEG、PNG、WebP）")
    return mime


def to_data_uri(data: bytes, mime: str) -> str:
    """
    把圖片位元組轉成可以直接放進 `<img src>` 的字串。

    參數
        data (bytes): 圖片內容。
        mime (str): MIME 型別，用 `sniff_type()` 或 `validate_avatar()` 取得。

    回傳
        str: 形如 `data:image/jpeg;base64,/9j/4AAQ...`

    範例
        >>> to_data_uri(b"\\xff\\xd8\\xff", "image/jpeg")[:22]
        'data:image/jpeg;base64'

    注意
        這是**最簡單的回傳方式**：前端拿到直接塞進 `<img src>` 就會顯示，
        不需要額外一支「取得圖片」的路由。

        代價是 base64 會讓資料變大約 33%，而且**不能被瀏覽器快取**。
        大頭貼很小所以沒差；如果之後要放大圖，就該改成獨立的圖片路由。
    """
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


def from_data_uri(uri: str, *, max_bytes: int = MAX_BYTES) -> tuple[bytes, str]:
    """
    把前端送來的 data URI 拆回位元組，**並且順便驗證**。

    參數
        uri (str): 形如 `data:image/jpeg;base64,....` 的字串。
        max_bytes (int): 大小上限。

    回傳
        tuple[bytes, str]: `(圖片位元組, MIME 型別)`。

    丟出
        InvalidImage: 格式不對、base64 壞掉、太大、或不是允許的圖片。

    範例
        >>> uri = to_data_uri(b"\\xff\\xd8\\xff" + b"0" * 50, "image/jpeg")
        >>> data, mime = from_data_uri(uri)
        >>> mime
        'image/jpeg'

    注意
        ⚠️ **回傳的 MIME 是重新嗅探出來的，不是信 URI 裡寫的那個。**

        使用者可以送 `data:image/jpeg;base64,<一個 Python 腳本>`——
        前面那段宣告是他自己寫的，不可信。
        我們只信 base64 解出來之後、檔案開頭的那幾個位元組。
    """
    if not uri or not uri.startswith("data:"):
        raise InvalidImage("格式不正確，需要 data URI")
    if "," not in uri:
        raise InvalidImage("格式不正確，找不到 base64 內容")

    _, _, payload = uri.partition(",")
    # base64 每 4 個字元還原成 3 個位元組，先估一下免得把超大的字串解出來
    if len(payload) * 3 // 4 > max_bytes * 2:
        raise InvalidImage(f"圖片太大了，最多 {max_bytes // 1024} KB")

    try:
        data = base64.b64decode(payload, validate=True)
    except Exception as exc:  # noqa: BLE001
        raise InvalidImage("base64 內容無法解碼") from exc

    mime = validate_avatar(data, max_bytes=max_bytes)
    return data, mime
