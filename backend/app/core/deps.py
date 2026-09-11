"""
依賴注入：把「每支路由都要做一次」的事情抽出來，寫一次就好。

✦ 負責人：成員1（認證與基礎建設）　✦ 分支：m1-auth
✦ **這是整個專案最關鍵的共用元件** —— `get_current_user` 沒好，
  其他三個人的路由一支都寫不下去。第 1 週的第一優先。

===========================================================================
什麼是依賴注入？用一個例子就懂
===========================================================================
想像每支需要登入的路由都要做這些事：

    1. 從請求標頭拿出 Authorization
    2. 檢查格式是不是 "Bearer xxxxx"
    3. 驗證 token 的簽名
    4. 檢查有沒有過期
    5. 從 token 裡拿出 user_id
    6. 去資料庫把這個使用者撈出來
    7. 確認這個帳號沒有被停用

三十七支路由每支都寫一次？不可能維護。而且只要有一支忘記寫，
那支就變成任何人都能打的漏洞。

FastAPI 的解法是：把這七步包成一個函式，路由這樣宣告——

    @router.get("/transactions")
    def list_transactions(me: User = Depends(get_current_user)):
        # 能走到這一行，代表上面七步都通過了，me 就是登入者
        ...

`Depends(get_current_user)` 的意思是「執行我之前，先幫我把這件事做完」。
如果驗證失敗，函式裡丟出 401，**路由的程式碼根本不會被執行**。

這就是依賴注入。你只要在參數上宣告「我需要什麼」，
FastAPI 負責在呼叫你之前把它準備好。

===========================================================================
依賴可以疊在一起
===========================================================================
看下面的 `require_master`：它自己也用了 `Depends(get_current_user)`。
FastAPI 會自動處理這個鏈：先跑 get_current_user，把結果餵給 require_master。

所以一支只有管理者能用的路由，只要寫：

    @router.post("/family/invite")
    def invite(me: User = Depends(require_master)):
        ...

「要登入」和「要是管理者」兩層檢查就都做完了。
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token

# HTTPBearer 會幫你從 Authorization 標頭裡把 "Bearer xxxxx" 的 xxxxx 取出來。
# 它同時也讓 /docs 頁面右上角出現一顆「Authorize」按鈕，
# 你可以在那裡貼上 token，之後在文件頁上試打 API 就會自動帶著它。
bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
):
    """
    確認請求帶著有效的登入權杖，並回傳對應的使用者。

    這是整個系統**最常被用到的依賴**，幾乎每支路由都會用它。

    失敗時一律回 401（未經驗證），並且訊息刻意講得模糊——
    不要告訴攻擊者「這個帳號存在但密碼錯」還是「這個帳號不存在」，
    那等於免費幫他確認哪些帳號是有效的。

    TODO(成員1): 目前只解 token，還沒真的去資料庫撈使用者。
                 等 models/user.py 完成後補上：
                   1. user = db.get(User, int(payload["sub"]))
                   2. 找不到或 user.is_active 是 False → 回 401
                   3. return user
    """
    if creds is None or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="請先登入",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_token(creds.credentials)
    except Exception as exc:  # noqa: BLE001  — 各種 JWT 錯誤一律當成未登入處理
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登入已過期，請重新登入",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    # 一定要檢查 type。否則攻擊者可以拿有效期 14 天的 refresh token
    # 當成 access token 用，等於繞過了「access token 只活 30 分鐘」的設計。
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="權杖型別不正確",
        )

    # TODO(成員1): 換成真的從資料庫撈使用者
    return {"id": int(payload["sub"]), "role": payload.get("role", "member")}


def require_master(me=Depends(get_current_user)):
    """
    只有家庭管理者（master）能通過。

    用在「邀請成員」「移除成員」「建立監管關係」這類敏感操作上。

    回 403（沒有權限）而不是 401（沒有登入）——這兩個要分清楚：
    - **401** 你還沒證明你是誰 → 前端應該把你導去登入頁
    - **403** 我知道你是誰，但你不能做這件事 → 前端應該顯示「權限不足」

    分錯的後果是前端會把「權限不足」的使用者一直踢回登入頁，
    他重新登入還是不能用，然後就來問你為什麼系統壞了。
    """
    if me.get("role") != "master":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="這個操作只有家庭管理者可以執行",
        )
    return me
