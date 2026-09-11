"""
密碼雜湊。包住 passlib，你不用讀它的文件。

===========================================================================
密碼為什麼不能直接存
===========================================================================
如果資料表存的是 `password = "abc123"`，那麼任何人看到資料庫
（被入侵、備份外流、甚至一個好奇的同事）就拿到了所有人的密碼。
更糟的是很多人到處用同一組密碼，等於連他的信箱也一起賠進去。

正確做法是存**雜湊值**：單向轉換，算得出去、回不來。

    "abc123"  ──bcrypt──>  "$2b$12$Kq3n...（60 個字元）"

驗證時不是把雜湊解回來（做不到），而是把這次輸入的密碼再算一次雜湊，
比對兩個雜湊值是否相同。

bcrypt 還有兩個特性值得知道：

1. **它故意很慢**（約 0.1 秒）。正常登入慢 0.1 秒沒感覺，
   但攻擊者想暴力猜一億組就會慢到不可行。
2. **它自動加鹽**。同樣的密碼 "abc123"，兩個使用者存進去的雜湊值不一樣，
   攻擊者不能一次破解所有人。

**絕對不要自己實作密碼雜湊。** 這是資安領域被寫爛的教訓。
"""

from __future__ import annotations

from passlib.context import CryptContext

__all__ = ["WeakPassword", "hash_password", "verify_password", "check_strength"]

# schemes 排最前面的是「新密碼用哪個演算法」，
# 後面的是「舊密碼還認得，驗證通過後自動升級」。
# 現在只有 bcrypt，之後要換演算法時這個機制會很有用。
_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

# bcrypt 只看密碼的前 72 個 byte，超過的部分會被默默忽略。
# 不擋的話，使用者設了 100 個字的密碼，其實只有前 72 byte 有效——
# 他以為自己很安全，其實不是。
_BCRYPT_MAX_BYTES = 72


class WeakPassword(ValueError):
    """
    密碼不符合強度要求時丟出。

    路由接到這個例外應該轉成 HTTP 422，並把 `str(exc)` 當成錯誤訊息回給前端——
    訊息已經寫成使用者看得懂的中文了。
    """


def check_strength(password: str, *, min_length: int = 8) -> None:
    """
    檢查密碼強度。**通過就靜靜回傳 None，不通過就丟例外。**

    參數
        password (str): 使用者輸入的明碼。
        min_length (int): 最短長度，預設 8。

    回傳
        None: 通過檢查。

    丟出
        WeakPassword: 不通過。訊息是中文的，可以直接回給前端。

    範例
        >>> check_strength("abc12345")      # 通過，沒有回傳值
        >>> check_strength("123")
        Traceback (most recent call last):
        WeakPassword: 密碼至少要 8 個字

    注意
        規則刻意很寬鬆：**只要求長度和「不要全是數字」**。
        強制大小寫、特殊符號那種規則在研究上已經被證明會讓使用者
        寫成 `Password1!` 這種更好猜的東西，反而更不安全。
    """
    if not password:
        raise WeakPassword("密碼不可以是空的")
    if len(password) < min_length:
        raise WeakPassword(f"密碼至少要 {min_length} 個字")
    if len(password.encode("utf-8")) > _BCRYPT_MAX_BYTES:
        raise WeakPassword(
            f"密碼太長了（bcrypt 只認得前 {_BCRYPT_MAX_BYTES} 個位元組，"
            "中文一個字算 3 個）"
        )
    if password.isdigit():
        raise WeakPassword("密碼不可以全部都是數字")


def hash_password(password: str, *, check: bool = True) -> str:
    """
    把明碼密碼轉成可以安全存進資料庫的雜湊值。

    參數
        password (str): 使用者輸入的明碼。
        check (bool): 是否順便檢查強度，預設 True。
            匯入既有資料之類的場合可以設 False。

    回傳
        str: 大約 60 個字元的雜湊字串。裡面已經包含鹽和演算法資訊，
            所以資料表只要存這一欄（`password_hash TEXT`）就夠。

    丟出
        WeakPassword: check=True 且密碼不符合強度要求。

    範例
        >>> h = hash_password("abc12345")
        >>> len(h) > 50 and h.startswith("$2b$")
        True
        >>> hash_password("abc12345") == hash_password("abc12345")
        False

    注意
        最後那個範例不是 bug：**同樣的密碼每次算出來的雜湊都不一樣**，
        因為每次的鹽不同。所以**不可以用 `==` 比對雜湊值**，
        一定要用 `verify_password()`。
    """
    if check:
        check_strength(password)
    return _ctx.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """
    確認使用者輸入的密碼對不對。

    參數
        password (str): 這次輸入的明碼。
        hashed (str): 資料庫裡存的雜湊值。

    回傳
        bool: 密碼正確就是 True。
            `hashed` 是空的或格式不對時回傳 False，**不會丟例外**——
            資料壞掉不該讓登入路由 500。

    範例
        >>> h = hash_password("abc12345")
        >>> verify_password("abc12345", h)
        True
        >>> verify_password("wrong", h)
        False
        >>> verify_password("abc12345", "")     # 壞資料不會爆
        False

    注意
        passlib 內部用的是**定時比較**，避免攻擊者從回應時間的
        微小差異推測密碼。所以不要自己改成 `==`。

        ⚠️ 登入路由要記得：**帳號不存在和密碼錯誤要回一樣的訊息**
        （「帳號或密碼不正確」）。分開講的話攻擊者可以拿一堆 email 來試，
        從回應差異整理出哪些帳號真的存在。
    """
    if not password or not hashed:
        return False
    try:
        return _ctx.verify(password, hashed)
    except Exception:  # noqa: BLE001 — 雜湊格式壞掉一律當成驗證失敗
        return False
