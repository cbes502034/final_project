"""
JWT 權杖。包住 PyJWT，你不用讀它的文件。

===========================================================================
為什麼需要權杖
===========================================================================
HTTP 是**無狀態**的：伺服器處理完一個請求就忘光了，
下一個請求進來時它不知道你是誰。那登入之後怎麼記住？

做法是發一張**有簽名的通行證**給你：

    eyJhbGciOiJIUzI1NiJ9 . eyJzdWIiOiIxIiwiZXhwIjoxNzY4fQ . 3vQ2n1k...
    └──── 標頭 ────┘   └──────── 內容 ────────┘   └─ 簽名 ─┘

之後每個請求都帶著它，伺服器驗簽名就知道是不是自己發的。

⚠️ **最重要的觀念：中間那段只是 base64 編碼，任何人都讀得到。**
複製貼到線上工具就解得開。所以**永遠不要把密碼、身分證字號放進去**。
JWT 保證的是「沒有人能竄改內容」，不是「沒有人看得到內容」。

===========================================================================
為什麼要兩種權杖
===========================================================================
    access token    30 分鐘   每次請求都帶。到處跑，外洩風險高 → 讓它快過期
    refresh token   14 天     只用來換新的 access token。存在資料庫，可以撤銷

access token **不存在資料庫裡，所以沒辦法主動撤銷**——這就是為什麼要設短。
refresh token 存在 `sessions` 表，登出時把它標記成作廢就好。

結果是：使用者不用每 30 分鐘重新登入（前端會自動續期），
但帳號被盜時撤銷 refresh token，攻擊者最多再撐 30 分鐘。

⚠️ **存進資料庫的不可以是 token 原文，要存雜湊值。**
道理跟密碼一樣：資料庫外洩時，攻擊者拿到原文就能直接冒用登入。
這個檔案有提供 `fingerprint()` 幫你算。
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.toolkit.config import settings

__all__ = [
    "TokenError",
    "TokenExpired",
    "WrongTokenType",
    "make_access_token",
    "make_refresh_token",
    "read_token",
    "read_access_token",
    "read_refresh_token",
    "fingerprint",
]


class TokenError(Exception):
    """
    權杖無效時丟出的共同父類別。

    路由接到它應該回 **401**（未經驗證），並且訊息講得模糊一點——
    不要告訴攻擊者到底是哪裡不對。
    """


class TokenExpired(TokenError):
    """權杖過期。前端收到這個應該去打 refresh。"""


class WrongTokenType(TokenError):
    """
    拿 refresh token 當 access token 用（或反過來）。

    ⚠️ **這個檢查不能省。** 沒檢查的話，攻擊者可以拿有效期 14 天的
    refresh token 當成 access token 用，等於繞過了
    「access token 只活 30 分鐘」的整個設計。
    """


def _encode(payload: dict[str, Any]) -> str:
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def make_access_token(user_id, *, extra: dict[str, Any] | None = None) -> str:
    """
    發一張短效的通行證給登入成功的使用者。

    參數
        user_id: 使用者 ID。會被轉成字串放進 JWT 的 `sub` 欄位。
        extra (dict | None): 想額外塞進去的資訊，例如 `{"role": "master"}`。
            讓前端不必每次都再打一次 `/me`。

    回傳
        str: 編碼後的 JWT 字串。

    範例
        >>> t = make_access_token(1, extra={"role": "master"})
        >>> read_access_token(t)["sub"]
        '1'

    注意
        ⚠️ **放進 extra 的東西任何人都讀得到**，不要放敏感資料。

        ⚠️ extra 是**發證當下的快照**。如果之後角色被改了，
        這張還沒過期的舊證裡仍然是舊角色。
        所以**權限判斷要以資料庫為準，不要只信 JWT 裡的角色**。
    """
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    if extra:
        payload.update(extra)
    return _encode(payload)


def make_refresh_token(user_id) -> tuple[str, datetime]:
    """
    發一張長效的續期憑證，同時回傳它的到期時間。

    參數
        user_id: 使用者 ID。

    回傳
        tuple[str, datetime]: `(token 字串, 到期時間)`。
            到期時間要一起存進 `sessions` 表，才能查詢「哪些登入還有效」。

    範例
        >>> t, exp = make_refresh_token(1)
        >>> read_refresh_token(t)["type"]
        'refresh'

    注意
        存進資料庫的要用 `fingerprint(token)` 算出來的雜湊值，**不是 token 原文**。
    """
    now = datetime.now(UTC)
    expires = now + timedelta(days=settings.refresh_token_days)
    token = _encode({"sub": str(user_id), "type": "refresh", "iat": now, "exp": expires})
    return token, expires


def read_token(token: str) -> dict[str, Any]:
    """
    驗證並解開一張權杖，回傳裡面的內容。

    參數
        token (str): JWT 字串。

    回傳
        dict: 權杖內容。至少會有 `sub`（使用者 ID，字串）與 `type`。

    丟出
        TokenExpired: 已經過期。
        TokenError: 簽名不對、格式錯誤、或根本不是 JWT。

    範例
        >>> t = make_access_token(7)
        >>> read_token(t)["sub"]
        '7'
        >>> read_token("亂打的東西")
        Traceback (most recent call last):
        TokenError: 權杖無效

    注意
        PyJWT 會自動檢查 `exp`，你不用手動比對時間。
    """
    try:
        return jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpired("權杖已過期") from exc
    except Exception as exc:  # noqa: BLE001 — 其他所有 JWT 錯誤一律當成無效
        raise TokenError("權杖無效") from exc


def read_access_token(token: str) -> dict[str, Any]:
    """
    解開一張 access token，並確認它真的是 access 型別。

    參數
        token (str): JWT 字串。

    回傳
        dict: 權杖內容。

    丟出
        TokenExpired / TokenError: 同 read_token。
        WrongTokenType: 這張是 refresh token，不是 access token。

    範例
        >>> t, _ = make_refresh_token(1)
        >>> read_access_token(t)
        Traceback (most recent call last):
        WrongTokenType: 這裡需要 access token，收到的是 refresh
    """
    payload = read_token(token)
    if payload.get("type") != "access":
        raise WrongTokenType(
            f"這裡需要 access token，收到的是 {payload.get('type')}"
        )
    return payload


def read_refresh_token(token: str) -> dict[str, Any]:
    """
    解開一張 refresh token，並確認它真的是 refresh 型別。

    參數
        token (str): JWT 字串。

    回傳
        dict: 權杖內容。

    丟出
        TokenExpired / TokenError / WrongTokenType

    注意
        ⚠️ **光通過這支還不夠。** 簽名有效只代表「這張是我們發的」，
        不代表「這張還能用」。使用者登出後那張 token 在過期前簽名仍然有效。

        所以 `/api/auth/refresh` 一定要再做兩件事：
        1. 用 `fingerprint(token)` 去 `sessions` 表找得到這筆
        2. 那筆的 `revoked_at` 還是 NULL（沒被登出過）
    """
    payload = read_token(token)
    if payload.get("type") != "refresh":
        raise WrongTokenType(
            f"這裡需要 refresh token，收到的是 {payload.get('type')}"
        )
    return payload


def fingerprint(token: str) -> str:
    """
    算出 token 的指紋，用來存進資料庫。

    參數
        token (str): JWT 字串。

    回傳
        str: 64 個字元的十六進位字串（SHA-256）。

    範例
        >>> t, _ = make_refresh_token(1)
        >>> len(fingerprint(t))
        64

    注意
        ⚠️ **`sessions` 表存這個，不要存 token 原文。**
        資料庫外洩時，攻擊者拿到原文就能直接冒用登入；
        拿到指紋則沒辦法反推回 token。

        這裡用 SHA-256 而不是 bcrypt，是因為 token 本身已經是高熵的隨機字串，
        不需要 bcrypt 那種「故意很慢」的防暴力破解設計——
        而且 refresh 每次請求都要查一次，太慢會影響體驗。
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
