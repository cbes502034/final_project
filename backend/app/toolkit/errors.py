"""
統一的錯誤回應。四個人用同一套，前端才不用為每支路由寫不同的處理。

===========================================================================
為什麼要統一
===========================================================================
不統一的話會變成這樣：

    成員1 回 {"error": "找不到"}
    成員2 回 {"message": "not found"}
    成員3 回 {"detail": "查無資料", "code": 404}
    成員4 直接 raise，回一串 Python 的錯誤堆疊

前端要為每支路由寫不同的錯誤處理，而且第四種還會**把內部細節吐給攻擊者**。

這個檔案把常用的錯誤包成一行就能用的函式，全部回傳 FastAPI 的
`HTTPException`，格式一律是 `{"detail": "訊息"}`。

===========================================================================
怎麼用
===========================================================================
    from app.toolkit import errors

    tx = db.get(Transaction, tx_id)
    if tx is None:
        raise errors.not_found("找不到這筆紀錄")

    if tx.user_id != me.id:
        raise errors.forbidden("你只能刪除自己的紀錄")

**注意是 `raise` 不是 `return`。** `return` 的話 HTTP 狀態碼還是 200，
前端的 `fetch` 不會進入錯誤分支，它會以為一切正常然後拿到一包看不懂的東西。
"""

from __future__ import annotations

from fastapi import HTTPException, status

__all__ = [
    "bad_request",
    "unauthorized",
    "forbidden",
    "not_found",
    "conflict",
    "unprocessable",
    "service_unavailable",
    "safe_message",
]


def bad_request(detail: str = "請求格式不正確") -> HTTPException:
    """
    400 —— 請求本身有問題，但不是欄位格式錯誤。

    參數
        detail (str): 給使用者看的中文訊息。

    回傳
        HTTPException: 要用 `raise` 丟出去。

    注意
        **欄位格式錯誤不要用這個**，Pydantic 會自動回 422 而且訊息更精確。
        400 留給「格式對但語意不合理」的情況，
        例如「起始日期比結束日期還晚」。
    """
    return HTTPException(status.HTTP_400_BAD_REQUEST, detail)


def unauthorized(detail: str = "請先登入") -> HTTPException:
    """
    401 —— **你還沒證明你是誰。**

    參數
        detail (str): 訊息。**刻意講得模糊**，不要透露是帳號不存在還是密碼錯。

    回傳
        HTTPException: 會自動帶上 `WWW-Authenticate: Bearer` 標頭。

    注意
        ⚠️ **401 和 403 不可以混用。**
        前端看到 401 會把使用者**導去登入頁**。

        ⚠️ 登入失敗時，**帳號不存在和密碼錯誤要回一樣的訊息**。
        分開講的話攻擊者可以拿一堆 email 來試，
        從回應差異整理出哪些帳號真的存在（帳號列舉攻擊）。
    """
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"}
    )


def forbidden(detail: str = "你沒有權限執行這個操作") -> HTTPException:
    """
    403 —— **我知道你是誰，但你不能做這件事。**

    參數
        detail (str): 訊息。這裡可以講清楚一點，因為對方已經通過身分驗證了。

    回傳
        HTTPException

    注意
        ⚠️ 前端看到 403 會顯示「權限不足」，**不會**導去登入頁。
        跟 401 分錯的話，權限不足的使用者會被一直踢回登入頁，
        他重新登入還是不能用。

        ⚠️ 查詢別人的資料沒權限時，**要回 403 不要回空陣列**。
        空陣列會讓使用者以為「對方這個月沒記帳」。
    """
    return HTTPException(status.HTTP_403_FORBIDDEN, detail)


def not_found(detail: str = "找不到這筆資料") -> HTTPException:
    """
    404 —— 東西不存在。

    參數
        detail (str): 訊息。

    回傳
        HTTPException

    注意
        有個微妙的取捨：如果資源存在但你沒權限看，要回 403 還是 404？

        - 回 **403** 比較誠實，但等於告訴對方「這個 ID 是存在的」
        - 回 **404** 比較安全，但使用者會困惑

        本專案的約定：**家庭內部一律回 403**（成員之間本來就知道彼此存在），
        跨家庭一律回 404（不該讓人探測別的家庭有哪些資料）。
    """
    return HTTPException(status.HTTP_404_NOT_FOUND, detail)


def conflict(detail: str = "資料衝突") -> HTTPException:
    """
    409 —— 跟現有資料衝突。

    參數
        detail (str): 訊息。

    回傳
        HTTPException

    範例
        註冊時 email 已經被用過：

            raise errors.conflict("這個 email 已經註冊過了")
    """
    return HTTPException(status.HTTP_409_CONFLICT, detail)


def unprocessable(detail: str = "資料內容不正確") -> HTTPException:
    """
    422 —— 格式對但值不合理。

    參數
        detail (str): 訊息。

    回傳
        HTTPException

    注意
        Pydantic 的欄位驗證會**自動**回 422，你不用自己寫。
        這支是給「Pydantic 驗不到、但業務邏輯上不合理」的情況用的，
        例如 `toolkit.money.InvalidAmount` 或
        `toolkit.period.InvalidPeriod` 接起來之後轉成 422。

        用法：

            from app.toolkit import errors, period

            try:
                start, end = period.month_range(p)
            except period.InvalidPeriod as exc:
                raise errors.unprocessable(str(exc)) from exc
    """
    return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail)


def service_unavailable(detail: str = "服務暫時無法使用，請稍後再試") -> HTTPException:
    """
    503 —— **我們沒壞，但依賴的服務現在不行。**

    參數
        detail (str): 訊息。

    回傳
        HTTPException

    注意
        ⚠️ 模型服務叫不動時**要回 503 不是 500**。

        500 的意思是「我們的程式壞了」，會觸發監控告警、
        會讓人以為要去修 bug。503 的意思是「暫時性的外部問題」，
        前端可以提示使用者稍後再試。
    """
    return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail)


def safe_message(exc: Exception, fallback: str = "系統發生錯誤") -> str:
    """
    把例外訊息轉成可以安全回給使用者的字串。

    參數
        exc (Exception): 接到的例外。
        fallback (str): 判斷為不安全時改用的訊息。

    回傳
        str: 我們自己定義的例外就回原訊息（那些訊息本來就寫給使用者看），
            其他一律回 fallback。

    範例
        >>> from app.toolkit.money import InvalidAmount
        >>> safe_message(InvalidAmount("金額不可以是負數"))
        '金額不可以是負數'
        >>> safe_message(KeyError("password_hash"))
        '系統發生錯誤'

    注意
        ⚠️ **不要直接把 `str(exc)` 回給前端。**

        資料庫的例外訊息長這樣：

            psycopg.errors.UniqueViolation: duplicate key value violates
            unique constraint "users_email_key"

        這等於免費告訴攻擊者：你用 PostgreSQL、表叫 users、
        有個唯一索引在 email 上。**這些都是他不需要知道的事。**
    """
    from app.toolkit.money import InvalidAmount
    from app.toolkit.passwords import WeakPassword
    from app.toolkit.period import InvalidPeriod

    safe_types = (InvalidAmount, InvalidPeriod, WeakPassword)
    if isinstance(exc, safe_types):
        return str(exc)
    return fallback
