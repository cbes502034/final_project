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
你們要建的目錄（自己 mkdir，不要等人給）
===========================================================================
    app/
    ├── models/      SQLAlchemy 資料表    繼承 toolkit.db.Base
    ├── schemas/     Pydantic 進出模型
    ├── routers/     路由，一組一個檔案
    └── services/    商業邏輯，路由只負責收送

誰負責哪一塊寫在 `app/ownership.py`，跑 `python -m app.ownership` 會印出來。

===========================================================================
加一組路由的三個步驟
===========================================================================
1. 建立 `app/routers/你的模組.py`：

       from fastapi import APIRouter, Depends
       from sqlalchemy.orm import Session
       from app.toolkit.db import get_db
       from app.toolkit.deps import current_user_id

       router = APIRouter()

       @router.get("/things")
       def list_things(uid: int = Depends(current_user_id),
                       db: Session = Depends(get_db)):
           ...

2. 在下面的 import 區塊解除註解
3. 在下面的 include_router 區塊解除註解

**這個檔案沒有單一主人**，四個人都會改。一次只加一行，衝突很好解，
但改之前還是在群組講一聲比較好。
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.toolkit.config import settings

# ---------------------------------------------------------------------------
# 路由寫好之後在這裡 import 進來
#
# from app.routers import auth          # 成員1
# from app.routers import family        # 成員4
# from app.routers import transactions  # 成員2
# from app.routers import nlp           # 成員2
# from app.routers import categories    # 成員3
# from app.routers import stats         # 成員3
# from app.routers import budgets       # 成員3
# from app.routers import advices       # 成員3
# ---------------------------------------------------------------------------


app = FastAPI(
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


# ---------------------------------------------------------------------------
# 路由寫好之後在這裡掛上
#
# prefix 會自動加在每支路由前面，所以 routers/auth.py 裡寫
# @router.post("/login")，實際網址就是 /api/auth/login。
# tags 是 /docs 頁面上的分組標籤。
#
# app.include_router(auth.router,         prefix="/api/auth", tags=["身分認證"])
# app.include_router(family.router,       prefix="/api",      tags=["家庭與權限"])
# app.include_router(transactions.router, prefix="/api",      tags=["記帳"])
# app.include_router(nlp.router,          prefix="/api/nlp",  tags=["段落記帳"])
# app.include_router(categories.router,   prefix="/api",      tags=["分類體系"])
# app.include_router(stats.router,        prefix="/api",      tags=["統計"])
# app.include_router(budgets.router,      prefix="/api",      tags=["預算與存款目標"])
# app.include_router(advices.router,      prefix="/api",      tags=["財務建議"])
# ---------------------------------------------------------------------------


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
