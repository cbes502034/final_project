"""
密碼雜湊與 JWT。所有跟「證明你是你」有關的低階工具都放這裡。

✦ 負責人：成員1（認證與基礎建設）　✦ 分支：m1-auth

===========================================================================
一、密碼為什麼不能直接存？
===========================================================================
如果資料表裡存的是 `password = "abc123"`，那麼任何人只要看到資料庫
（被入侵、備份外流、甚至一個好奇的同事），就拿到了所有人的密碼。
更糟的是，很多人到處用同一組密碼，等於連他的信箱也一起賠進去。

正確做法是存**雜湊值**：一種單向的轉換，算得出去、回不來。

    "abc123"  ──bcrypt──>  "$2b$12$Kq3n...（60 個字元）"

驗證的時候不是把雜湊值解回來（做不到），而是把使用者這次輸入的密碼
再算一次雜湊，比對兩個雜湊值是否相同。

**bcrypt 還有兩個特性值得知道：**
1. 它故意設計得很慢（大約 0.1 秒）。正常登入慢 0.1 秒沒感覺，
   但攻擊者想暴力猜一億組密碼就會慢到不可行。
2. 它會自動加「鹽」（隨機字串）。所以同樣的密碼 "abc123"，
   兩個使用者存進去的雜湊值是不一樣的——攻擊者不能一次破解所有人。

**絕對不要自己實作密碼雜湊。** 這是資安領域被寫爛的教訓，
自己寫的幾乎一定有洞，直接用 passlib 就好。

===========================================================================
二、JWT 是什麼？
===========================================================================
HTTP 是「無狀態」的：伺服器處理完一個請求就忘光了，
下一個請求進來時它不知道你是誰。那登入之後怎麼記住？

JWT（JSON Web Token）的做法是發一張**有簽名的通行證**給你：

    eyJhbGciOiJIUzI1NiJ9 . eyJzdWIiOiIxIiwiZXhwIjoxNzY4fQ . 3vQ2n1k...
    └──── 標頭 ────┘   └──────── 內容 ────────┘   └─ 簽名 ─┘

- **標頭**：用什麼演算法簽的
- **內容**：你是誰、什麼時候過期（這段只是 base64 編碼，**任何人都讀得到**）
- **簽名**：用 JWT_SECRET 算出來的，**只有伺服器算得出來**

之後每次請求你都帶著這張通行證，伺服器驗簽名就知道是不是自己發的。

**最重要的觀念：JWT 的內容是公開的，不是加密的。**
所以永遠不要把密碼、身分證字號放進 JWT。
它保證的是「沒有人能竄改內容」，不是「沒有人看得到內容」。

===========================================================================
三、為什麼要有兩種 token？
===========================================================================
- **access token**：有效期短（30 分鐘），每次請求都帶著。
  因為它到處跑，外洩風險高，所以讓它很快過期。
  它不存在資料庫裡，**所以沒辦法主動撤銷**——這就是為什麼要設短。

- **refresh token**：有效期長（14 天），只在換新 access token 時用一次。
  它存在資料庫的 sessions 表裡，**所以登出時可以把它標記成作廢**。

這樣設計的結果是：使用者不用每 30 分鐘重新登入一次（前端會自動續期），
但如果帳號被盜，管理者撤銷 refresh token 之後，攻擊者最多再撐 30 分鐘。
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from passlib.context import CryptContext

from app.core.config import settings

# schemes 可以放多個，排最前面的是「新密碼要用哪個演算法」，
# 後面的是「舊密碼還認得，但驗證通過後會自動升級」。
# 現在只有 bcrypt 一個，之後要換演算法時這個機制會很有用。
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    """
    把明碼密碼轉成可以安全存進資料庫的雜湊值。

    註冊、修改密碼時呼叫這支。回傳的字串大約 60 個字元，
    裡面已經包含了鹽和演算法資訊，所以資料表只要存這一欄就夠。
    """
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """
    確認使用者輸入的密碼對不對。

    `plain` 是這次輸入的明碼，`hashed` 是資料庫裡存的雜湊值。
    回傳 True 代表密碼正確。

    注意：**不要自己用 == 比對**。passlib 內部用的是
    「定時比較」，避免攻擊者從回應時間的微小差異推測出密碼。
    """
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: int, extra: dict[str, Any] | None = None) -> str:
    """
    發一張短效的通行證給登入成功的使用者。

    `user_id` 會被放進 JWT 的 `sub`（subject，也就是「這張證是誰的」）欄位。
    `extra` 可以塞額外資訊，例如角色，讓前端不必每次都再打一次 /me。

    ⚠️ 提醒：放進 extra 的東西是**任何人都讀得到**的，
    而且它是發證當下的快照——如果之後角色被改了，
    這張還沒過期的舊證裡仍然是舊角色。
    所以**權限判斷要以資料庫為準，不要只信 JWT 裡的角色**。
    """
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,                                              # 什麼時候發的
        "exp": now + timedelta(minutes=settings.access_token_minutes),  # 什麼時候過期
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: int) -> tuple[str, datetime]:
    """
    發一張長效的續期憑證，同時回傳它的到期時間。

    回傳兩個值：`(token 字串, 到期時間)`。
    到期時間要一起存進 sessions 資料表，這樣才能查詢「哪些登入還有效」。

    ⚠️ 存進資料庫的**不可以是 token 原文，要存雜湊值**。
    道理跟密碼一樣：萬一資料庫外洩，攻擊者拿到原文就能直接冒用登入。
    """
    now = datetime.now(UTC)
    expires = now + timedelta(days=settings.refresh_token_days)
    token = jwt.encode(
        {"sub": str(user_id), "type": "refresh", "iat": now, "exp": expires},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    return token, expires


def decode_token(token: str) -> dict[str, Any]:
    """
    驗證並解開一張 token，回傳裡面的內容。

    如果簽名不對、格式錯誤或已經過期，會丟出 `jwt.PyJWTError`
    （過期時是它的子類別 `jwt.ExpiredSignatureError`）。
    **呼叫的人要自己接起來**並轉成 401 回給前端——
    core/deps.py 裡的 `get_current_user` 就是這樣做的。

    PyJWT 會自動檢查 `exp` 欄位，不需要你手動比對時間。
    """
    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
    )
