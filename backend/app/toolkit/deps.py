"""
FastAPI 依賴。放「每支路由都要做一次」的事情。

===========================================================================
什麼是依賴注入？一個例子就懂
===========================================================================
每支需要登入的路由都要做這七件事：

    1. 從標頭拿出 Authorization      5. 拿出 user_id
    2. 檢查格式是不是 "Bearer xxx"   6. 去資料庫撈使用者
    3. 驗證簽名                      7. 確認帳號沒被停用
    4. 檢查有沒有過期

三十幾支路由每支都寫一次？不可能維護。而且**只要有一支忘記寫，
那支就變成任何人都能打的漏洞**。

FastAPI 的解法是把它包成一個函式，路由這樣宣告：

    @router.get("/transactions")
    def list_transactions(uid: int = Depends(current_user_id)):
        # 能執行到這一行，代表驗證都通過了
        ...

如果驗證失敗，函式裡會丟出 401，**路由的程式碼一行都不會被執行**。

===========================================================================
⚠️ 這個檔案只做到第 5 步，第 6、7 步是你們的
===========================================================================
因為第 6 步要用到 `User` 資料表，**而那是你們自己定義的**。
工具箱不知道你的表長什麼樣，也不該知道。

所以這裡提供 `current_user_id` —— 它回傳一個**已經驗證過的使用者 ID**。
你們在自己的程式裡這樣包一層：

    # 你們的 app/deps.py
    from fastapi import Depends
    from sqlalchemy.orm import Session
    from app.toolkit.deps import current_user_id
    from app.toolkit.db import get_db
    from app.toolkit import errors
    from app.models.user import User

    def get_current_user(
        uid: int = Depends(current_user_id),
        db: Session = Depends(get_db),
    ) -> User:
        user = db.get(User, uid)
        if user is None or not user.is_active:
            raise errors.unauthorized()
        return user

這樣切的好處是：**工具箱不綁你的資料模型**，你換掉 User 的定義也不用改它。
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.toolkit import errors, tokens

__all__ = ["bearer", "current_user_id", "current_token_payload", "Paging", "paging"]

# HTTPBearer 會幫你從 Authorization 標頭把 "Bearer xxxxx" 的 xxxxx 取出來。
# auto_error=False 是刻意的：我們要自己控制錯誤訊息，
# 不要用它預設的英文訊息。
#
# 它同時讓 /docs 頁面右上角出現一顆「Authorize」按鈕，
# 你可以在那裡貼上 token，之後在文件頁上試打 API 就會自動帶著它。
bearer = HTTPBearer(auto_error=False, description="登入後拿到的 access token")


def current_token_payload(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> dict:
    """
    驗證請求帶的 access token，回傳解開後的內容。

    參數
        creds: FastAPI 自動注入，你不用傳。

    回傳
        dict: 權杖內容。至少有 `sub`（使用者 ID，**字串**）與 `type`。
            如果發證時塞了 `role`，這裡也拿得到。

    丟出
        HTTPException(401): 沒帶權杖、格式不對、過期、或型別不是 access。

    範例
        @router.get("/whoami")
        def whoami(payload: dict = Depends(current_token_payload)):
            return {"id": payload["sub"], "role": payload.get("role")}

    注意
        ⚠️ payload 裡的 `role` 是**發證當下的快照**。
        如果之後角色被改了，這張還沒過期的舊證裡仍然是舊角色。
        **權限判斷要以資料庫為準，不要只信這裡的 role。**
    """
    if creds is None or not creds.credentials:
        raise errors.unauthorized("請先登入")
    try:
        return tokens.read_access_token(creds.credentials)
    except tokens.TokenExpired as exc:
        raise errors.unauthorized("登入已過期，請重新登入") from exc
    except tokens.TokenError as exc:
        raise errors.unauthorized("登入資訊無效，請重新登入") from exc


def current_user_id(payload: dict = Depends(current_token_payload)) -> int:
    """
    取得目前登入者的 ID。**這是最常用的一支。**

    參數
        payload: 自動注入。

    回傳
        int: 使用者 ID。

    丟出
        HTTPException(401): 驗證失敗，或 `sub` 不是數字。

    範例
        @router.get("/transactions")
        def list_tx(uid: int = Depends(current_user_id), db: Session = Depends(get_db)):
            return db.query(Transaction).filter(Transaction.user_id == uid).all()

    注意
        JWT 的 `sub` 依規範是字串，所以這裡幫你轉成 int。
        如果你的主鍵是 UUID 之類的非整數型別，請改用
        `current_token_payload` 自己取 `payload["sub"]`。
    """
    raw = payload.get("sub")
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise errors.unauthorized("登入資訊無效，請重新登入") from exc


@dataclass(frozen=True)
class Paging:
    """
    分頁參數。由 `paging` 依賴產生，你不用自己建。

    屬性
        page (int): 第幾頁，從 1 開始。
        size (int): 每頁幾筆。
        offset (int): 丟給 SQL 的 OFFSET，已經幫你算好。
        limit (int): 丟給 SQL 的 LIMIT，等於 size。
    """

    page: int
    size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size

    @property
    def limit(self) -> int:
        return self.size


def paging(
    page: int = Query(1, ge=1, description="第幾頁，從 1 開始"),
    size: int = Query(50, ge=1, le=200, description="每頁幾筆，最多 200"),
) -> Paging:
    """
    把 `?page=2&size=50` 轉成可以直接用的分頁參數。

    參數
        page (int): 第幾頁。小於 1 會被 FastAPI 自動擋下回 422。
        size (int): 每頁幾筆。超過 200 也會被擋下。

    回傳
        Paging: 帶著 `offset` 與 `limit` 的物件。

    範例
        @router.get("/transactions")
        def list_tx(p: Paging = Depends(paging), db: Session = Depends(get_db)):
            q = db.query(Transaction)
            total = q.count()
            rows = q.offset(p.offset).limit(p.limit).all()
            return {"transactions": rows, "total": total}

    注意
        ⚠️ **`size` 一定要有上限。** 沒有上限的話，
        有人打 `?size=999999` 就能讓你的資料庫一次撈出全部資料，
        記憶體爆掉、服務掛掉。這叫資源耗盡攻擊，防起來只要一行 `le=200`。

        ⚠️ 回傳時記得帶 `total`，前端才畫得出分頁器。
        `total` 要在套用 offset/limit **之前**算。
    """
    return Paging(page=page, size=size)
