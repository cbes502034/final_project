"""
資料庫連線。整個專案只有這裡會建立連線，其他地方一律透過 `get_db` 拿。

✦ 負責人：成員1（認證與基礎建設）　✦ 分支：m1-auth
✦ **這是共用元件，四個人的每一支路由都要用，第 1 週要最優先完成**

===========================================================================
三個名詞先講清楚
===========================================================================
**Engine（引擎）**
    整個程式只會有一個。它管理一池連線，你要用的時候跟它借，用完還回去。
    為什麼要「池」？因為每開一條新的資料庫連線都要花掉好幾十毫秒，
    開開關關非常浪費。連線池讓你重複使用已經開好的連線。

**Session（工作階段）**
    一次請求用一個。你所有的查詢、新增、修改都透過它，
    最後 `commit()` 一次把變更寫進去，或 `rollback()` 全部取消。
    可以想成「購物車」：你把要做的事情一件件放進去，結帳時才真的送出。

**Base（基底類別）**
    所有資料表定義（models/ 底下那些）都要繼承它，
    SQLAlchemy 才知道「這個類別代表一張資料表」。

===========================================================================
為什麼要用 yield 而不是 return？
===========================================================================
看下面 `get_db` 的寫法，它是 `yield db` 而不是 `return db`。
差別在於：yield 之後的程式碼會在「請求處理完之後」才執行。

所以流程是這樣：

    請求進來 → 建立 session → yield 給路由用 → 路由跑完 → 回來關掉 session

**這保證了不管路由成功還是丟出例外，session 都一定會被關掉。**
忘記關 session 是後端最常見的資源洩漏，寫成這樣就不會有這個問題。
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """
    所有資料表的共同祖先。

    models/ 底下每一個類別都要 `class User(Base):` 這樣繼承它。
    SQLAlchemy 會蒐集所有繼承 Base 的類別，才知道要建哪些表。
    """


engine = create_engine(
    settings.database_url,
    # 每次從池子裡拿連線前先確認它還活著。
    # Render 的免費 PostgreSQL 會把閒置太久的連線切斷，
    # 沒有這個設定的話，服務閒置一陣子後第一個請求就會失敗。
    pool_pre_ping=True,
    # 連線活超過 5 分鐘就換一條新的，同樣是為了避開被切斷的舊連線
    pool_recycle=300,
    # 設成 True 會把實際送出的 SQL 印出來，除錯時很好用，
    # 但正式環境會把 log 灌爆，所以關著
    echo=False,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,   # 一定要自己呼叫 commit()，避免不小心寫入
    autoflush=False,    # 不要偷偷送出查詢，行為比較好預測
    expire_on_commit=False,  # commit 之後物件還能繼續讀，不會變成「過期」狀態
)


def get_db() -> Generator[Session, None, None]:
    """
    提供一個資料庫工作階段給路由使用，用完自動關閉。

    在路由裡這樣用：

        from fastapi import Depends
        from sqlalchemy.orm import Session
        from app.core.database import get_db

        @router.get("/something")
        def read_something(db: Session = Depends(get_db)):
            return db.query(User).all()

    `Depends(get_db)` 的意思是「請 FastAPI 幫我準備好一個 db 再叫我」。
    你完全不用自己建立或關閉，FastAPI 會處理掉。
    這個機制叫做**依賴注入**，是 FastAPI 最核心的概念，
    在 core/deps.py 裡還會用它做權限檢查。
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
