"""
應用程式的入口。整個後端從這個檔案開始跑。

===========================================================================
現在這個檔案幾乎是空的，這是刻意的
===========================================================================
`app/toolkit/` 底下的工具已經寫好了，**但路由、資料表、商業邏輯是你們要寫的**。

這裡現在只有：建立 app、設定 CORS、一支健康檢查。
你們每完成一組路由，就回來加一行 `include_router`。

===========================================================================
怎麼跑起來
===========================================================================
    cd backend
    pip install -r requirements.txt
    cp .env.example .env          # 然後把 .env 裡的值填一填
    uvicorn app.main:app --reload

打開 http://localhost:8000/docs ——
FastAPI 自動產生的互動式文件，**可以直接在上面送出請求試打**，
不需要寫前端也不需要 Postman。

===========================================================================
目錄（都建好了）
===========================================================================
    app/
    ├── models/      SQLAlchemy 資料表（22 張，欄位跟 frontend/js/data.js 的 schema 對齊）
    ├── schemas/     Pydantic 請求主體（欄位名字跟前端送的一樣）
    ├── routers/     路由，一個領域一個資料夾（auth／ledger／analytics／access）——
    │                每一支都先回 501，守衛與主體模型已經接好
    ├── services/    商業邏輯（analytics 算錢、permission 可見範圍、llm 呼叫模型）
    ├── guards.py    路由守衛（仿 MineMarket 的 AuthDecorator）
    ├── catalog.py   固定清單（角色、權限表、理財選項、系統分類），正本是 frontend/js/data.js
    ├── cli.py       python -m app.cli：init-env、check-config、init-db、make-admin
    └── toolkit/     已經寫好的工具：config、db、crud（增刪改查）、scope、ledger…

誰負責哪一支寫在 `app/ownership.py`，`python -m app.ownership` 會列出每個人還剩幾支。

===========================================================================
做完一支路由
===========================================================================
在 app/routers/<你的資料夾>/ 找到那個函式，刪掉 `@stub`，把 `raise not_ready(...)` 那一行換成說明字串的第二步。
這個檔案不用動——所有 router 已經掛上了（下面的 include_router）。
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.toolkit import security
from app.toolkit.config import settings

from app import routers

log = logging.getLogger("fambudget")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """服務啟動時：把 ADMIN_EMAILS 的帳號設成平台管理員。

    Render 免費方案沒有 Shell 可以下 python -m app.cli make-admin，所以啟動時自己跑一次。
    已經加入家庭或記過帳的帳號不會被設（見 cli.promote_admins）。資料庫連不上也不能讓服務起不來。
    """
    if settings.admin_email_list:
        try:
            from app.cli import promote_admins
            for line in await run_in_threadpool(promote_admins, settings.admin_email_list):
                log.info("平台管理員：%s", line)
        except Exception:            # noqa: BLE001
            log.exception("設定平台管理員失敗")
    yield


app = FastAPI(
    lifespan=lifespan,
    title="家庭記帳與財務控管系統 API",
    description=(
        "四人六週專題的後端。\n\n"
        "分工寫在 `app/ownership.py`，跑 `python -m app.ownership` 會印出分工表。\n\n"
        "**串接前端之前請先讀 `docs/02-前後端串接契約.md`** —— "
        "那份寫清楚每一支「前端送什麼、你要吐什麼、前端拿去幹嘛」，"
        "而且是從前端程式實際跑出來的，不是手寫的。"
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


# ===========================================================================
# CORS：瀏覽器的安全機制，一定要設對，不然前端會收到看不懂的錯誤
# ===========================================================================
# 瀏覽器規定：網頁 A 的 JavaScript 要去打網站 B 的 API，
# 網站 B 必須明講「我允許 A 來打我」，否則瀏覽器會直接擋下來。
#
# 我們的前端在 fambudget-web.onrender.com，後端在另一個網域，所以一定要設。
#
# 最常見的卡關：前端 console 出現 "blocked by CORS policy"，
# 九成是 ALLOWED_ORIGINS 沒填對 —— 網址要完整（含 https://），結尾不要加斜線。
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===========================================================================
# 沒接住的錯誤：一律回 JSON 的 500
# ===========================================================================
# 前端只會讀 {"detail": ...}；回純文字的話，畫面只能寫「HTTP 500」。
# ⚠️ 正式環境（APP_ENV=production）只回一句話——例外訊息可能帶著表名、欄位、SQL，
#    那些是攻擊者不需要知道的事（見 toolkit/errors.py 的 safe_message）。
#    開發環境多附上例外的類型與訊息，組員才知道錯在哪；完整的追蹤一律寫進 log。
# 另外記一筆 error_logs，平台管理頁即時看得到（只記第一行，SQL 與參數切掉——參數裡可能有金額）。
def _where(request: Request) -> tuple[str, str | None]:
    """出錯的路由（樣板，例如 /api/transactions/{tx_id}）與函式名稱。"""
    route = request.scope.get("route")
    endpoint = request.scope.get("endpoint")
    return (getattr(route, "path", None) or request.url.path), getattr(endpoint, "__name__", None)


def _first_line(exc: Exception) -> str:
    text = str(exc).split("\n")[0].split("[SQL:")[0].split("[parameters:")[0].strip()
    return ("%s: %s" % (type(exc).__name__, text) if text else type(exc).__name__)[:300]


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    log.exception("未預期的錯誤：%s %s", request.method, request.url.path)
    path, fn = _where(request)
    await run_in_threadpool(security.log_error, "server", _first_line(exc), status=500, method=request.method,
                            path=path, location=fn, user_id=security.user_from(request))
    detail = "系統發生錯誤，請稍後再試"
    if not settings.is_production:
        detail += "（開發環境才看得到：%s: %s）" % (type(exc).__name__, exc)
    return JSONResponse(status_code=500, content={"detail": detail})


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    """路由自己丟的 5xx（例如模型叫不動的 503）也記進 error_logs；回應照 FastAPI 原本的樣子。"""
    if exc.status_code >= 500:
        path, fn = _where(request)
        await run_in_threadpool(security.log_error, "server", str(exc.detail)[:300], status=exc.status_code,
                                method=request.method, path=path, location=fn, user_id=security.user_from(request))
    return await http_exception_handler(request, exc)


# ---------------------------------------------------------------------------
# 路由：12 組全部掛上，prefix 一律 /api（每個檔案裡寫的是 /api 後面那段）。
# 還沒做的那幾支會回 501，前端會講出是哪一支、誰負責。
# ---------------------------------------------------------------------------
for module in routers.ALL:
    app.include_router(module.router, prefix="/api")


@app.get("/healthz", tags=["系統"])
async def healthz() -> dict[str, str]:
    """
    健康檢查。

    Render 固定打這支確認服務還活著，連續失敗會判定掛掉並重啟。

    這支刻意做得很單純 —— **不查資料庫、不呼叫模型**。
    它的任務只是回答「這個程式還在跑嗎」。
    把資料庫查詢寫進來的話，資料庫一慢就會被誤判成服務掛掉。
    """
    return {"status": "ok", "service": "fambudget-backend"}
