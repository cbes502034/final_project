"""
應用程式的入口。整個後端從這個檔案開始跑。

===========================================================================
這個檔案在做什麼？
===========================================================================
你可以把它想成一棟大樓的「大門與樓層配置圖」：

1. 建立 FastAPI 這個應用程式物件（等於蓋好大樓）
2. 設定 CORS（等於決定哪些外面的人可以進來）
3. 把各個 router 掛上去（等於告訴訪客「三樓是會計部、五樓是業務部」）
4. 提供 /healthz 讓 Render 確認服務還活著

**請不要在這個檔案裡寫任何商業邏輯。**
這裡只負責「組裝」，實際做事的程式碼在 routers/ 和 services/。
這樣做的好處是：任何人打開 main.py，三十秒內就能看懂整個系統有哪些功能。

===========================================================================
怎麼把這個服務跑起來？
===========================================================================
    cd backend
    pip install -r requirements.txt
    uvicorn app.main:app --reload

`app.main:app` 的意思是「app 資料夾裡的 main.py 檔案裡，那個叫 app 的變數」。
`--reload` 是指存檔後自動重新啟動，開發時很方便，正式環境不要開。

跑起來之後打開 http://localhost:8000/docs ，
你會看到 FastAPI 自動幫你產生的互動式 API 文件，可以直接在上面送出請求。
**這是 FastAPI 最值錢的功能之一，不需要你寫任何一行文件。**
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import (
    advices,
    auth,
    budgets,
    family,
    nlp,
    stats,
    transactions,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    服務啟動與關閉時要做的事。

    `yield` 前面的程式碼在「服務啟動時」跑一次，
    `yield` 後面的程式碼在「服務關閉時」跑一次。

    例如：啟動時建立資料庫連線池、關閉時把連線收乾淨。
    現在還沒有需要在這裡做的事，先留著架構。
    """
    # TODO(成員1): 若之後需要在啟動時預載模型設定或檢查資料庫連線，寫在這裡
    yield
    # TODO(成員1): 若之後開了背景工作或連線池，在這裡收尾


app = FastAPI(
    title="家庭記帳與財務控管系統 API",
    description=(
        "四人一個月專題的後端。\n\n"
        "路由依功能模組分成七組，每組由一位成員負責——"
        "誰負責哪一組寫在每個 router 檔案的最上面。"
    ),
    version="0.1.0",
    lifespan=lifespan,
    # 這三個路徑就是自動產生的文件，正式環境若不想公開可以設成 None
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
# 我們的前端在 llm-capstone-top20.onrender.com，
# 後端在 fambudget-api.onrender.com，兩個網域不同，所以一定要設。
#
# 常見的卡關：前端 console 出現 "blocked by CORS policy"，
# 九成是這裡的網址沒填對（少了 https://、多了結尾的斜線都會失敗）。
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===========================================================================
# 掛上各模組的路由
# ---------------------------------------------------------------------------
# include_router 的意思是「把這個檔案裡定義的所有路由，都加到主程式上」。
# prefix 會自動加在每一支路由前面，所以 routers/auth.py 裡寫 @router.post("/login")，
# 實際的網址就是 /api/auth/login。
#
# tags 是給自動文件用的分類標籤，打開 /docs 就會看到照這個分組。
# ===========================================================================
app.include_router(auth.router, prefix="/api/auth", tags=["身分認證"])
app.include_router(family.router, prefix="/api", tags=["家庭與權限"])
app.include_router(transactions.router, prefix="/api", tags=["記帳"])
app.include_router(nlp.router, prefix="/api/nlp", tags=["段落記帳（模型）"])
app.include_router(stats.router, prefix="/api", tags=["統計"])
app.include_router(budgets.router, prefix="/api", tags=["預算與存款目標"])
app.include_router(advices.router, prefix="/api", tags=["財務建議"])


@app.get("/healthz", tags=["系統"])
async def healthz() -> dict[str, str]:
    """
    健康檢查。

    Render 會固定打這支路由來確認服務還活著；
    如果連續失敗，它會判定服務掛掉並重啟。

    這支刻意做得很單純——不查資料庫、不呼叫模型，
    因為它的任務只是回答「這個程式還在跑嗎」。
    如果把資料庫查詢也寫進來，資料庫一慢就會被誤判成服務掛掉。
    """
    return {"status": "ok", "service": "fambudget-api"}
