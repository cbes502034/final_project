"""
資料庫連線。整個專案只有這裡會建立連線，其他地方一律透過這裡拿。

✦ 負責人：成員1（認證與基礎建設）　✦ 分支：m1-auth
✦ **這是共用元件，四個人的每一支路由都要用**

===========================================================================
三種拿連線的方式，挑一種就好
===========================================================================
    1. 路由裡：Depends(get_db)                       ← 最常用
           @router.get("/things")
           def list_things(db: Session = Depends(get_db)): ...

    2. 一段程式要一起成功或一起失敗：with session_scope() as db
           with session_scope() as db:
               db.add(a); db.add(b)          # 離開 with 時自動 commit；出錯自動 rollback

    3. 包一個函式：@db_transaction（跟 MineMarket 的 db.py 同一個想法）
           @db_transaction
           def rename_user(db, user_id, name):   # 第一個參數自動塞進 session
               db.get(User, user_id).display_name = name
           rename_user(3, "王小明")               # 呼叫時不用傳 db
       MineMarket 是每次開一條 pymysql 連線、塞 cursor；
       這裡是從連線池借一個 SQLAlchemy Session——一樣自動 commit／rollback／關閉，但不會每次重連。

⚠️ 已經有 db 的時候（例如路由裡），把它傳下去，不要在裡面再開一個——
   兩個 session 各自 commit，就不是「一起成功或一起失敗」了。
   toolkit/crud.py 的每一支都收 db=...，傳了就用你的、不 commit，交給你決定。

===========================================================================
三個名詞
===========================================================================
**Engine**  整個程式一個，管理一池連線。開連線要幾十毫秒，所以用借的。
**Session** 一次請求一個。所有查詢、新增、修改都透過它，最後 commit 或 rollback。
**Base**    所有資料表類別（app/models/）都繼承它，SQLAlchemy 才知道要建哪些表。

===========================================================================
PostgreSQL 與 SQLite
===========================================================================
正式環境是 PostgreSQL。本機沒裝的話 DATABASE_URL 可以先填 sqlite:///./dev.db，
測試用 sqlite://（記憶體）。兩種都走這裡，差異（連線池、同執行緒檢查）這裡處理掉。
"""

from __future__ import annotations

import functools
from collections.abc import Callable, Generator, Iterator
from contextlib import contextmanager
from typing import Any, TypeVar

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.toolkit.config import settings

__all__ = [
    "Base", "engine", "SessionLocal", "get_db", "session_scope", "db_transaction",
    "make_engine", "use_database", "create_all", "drop_all",
]

T = TypeVar("T")


class Base(DeclarativeBase):
    """所有資料表的共同祖先。app/models/ 底下每一個類別都 `class User(Base):`。"""


def make_engine(url: str, *, echo: bool | None = None) -> Engine:
    """依網址建立 engine。PostgreSQL 開連線池；SQLite 處理掉它的限制。"""
    echo = settings.db_echo if echo is None else echo
    if url.startswith("sqlite"):
        memory = url in ("sqlite://", "sqlite:///:memory:")
        eng = create_engine(
            url, echo=echo,
            # SQLite 預設不讓別的執行緒用同一條連線；FastAPI 的測試客戶端會跨執行緒
            connect_args={"check_same_thread": False},
            # 記憶體資料庫每條連線都是一顆新的，所以只能用同一條
            poolclass=StaticPool if memory else None,
        )

        @event.listens_for(eng, "connect")
        def _fk_on(dbapi_conn, _):        # SQLite 預設不檢查外鍵，打開才跟 PostgreSQL 行為一致
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

        return eng
    return create_engine(
        url, echo=echo,
        # 每次借連線前先確認還活著：Render 免費 PostgreSQL 會切斷閒置太久的連線
        pool_pre_ping=True,
        # 連線活超過 5 分鐘就換新的，一樣是避開被切斷的舊連線
        pool_recycle=300,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_pool_size,
    )


engine: Engine = make_engine(settings.database_url)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,        # 一定要自己 commit，避免不小心寫入
    autoflush=False,         # 不要偷偷送出查詢，行為比較好預測
    expire_on_commit=False,  # commit 之後物件還能繼續讀
)


def use_database(url: str) -> Engine:
    """換一顆資料庫（測試、CLI 用）。之後 get_db／session_scope／crud 都用新的那顆。

        from app.toolkit import db
        db.use_database("sqlite://")
        db.create_all()
    """
    global engine
    engine = make_engine(url)
    SessionLocal.configure(bind=engine)
    return engine


def _load_models() -> None:
    """建表之前要先 import 所有 models，Base 才知道有哪些表。"""
    import app.models  # noqa: F401


def create_all() -> None:
    """照 app/models/ 建出所有表。⚠️ 正式環境用 Alembic 遷移（alembic upgrade head），這支給本機與測試。"""
    _load_models()
    Base.metadata.create_all(bind=engine)


def drop_all() -> None:
    """刪掉所有表。只給測試用。"""
    _load_models()
    Base.metadata.drop_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    路由用：`db: Session = Depends(get_db)`。請求結束一定關掉（yield 之後的程式在請求處理完才跑）。

    ⚠️ 這支**不會自動 commit**——路由自己決定什麼時候 commit，
       或是改用 toolkit/crud.py，它在沒有外層交易時會自己 commit。
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope(db: Session | None = None) -> Iterator[Session]:
    """
    一段要「一起成功或一起失敗」的程式。

        with session_scope() as db:
            ...                         # 正常離開 → commit；丟例外 → rollback 後照樣丟出去

    傳入既有的 db 時：直接用它、**不 commit 也不關**——外面那層交易說了算。
    """
    if db is not None:
        yield db
        return
    own = SessionLocal()
    try:
        yield own
        own.commit()
    except Exception:
        own.rollback()
        raise
    finally:
        own.close()


def db_transaction(fn: Callable[..., T]) -> Callable[..., T]:
    """
    把一個函式包成一個交易，session 自動塞進第一個參數（MineMarket 的 @db_transaction）。

        @db_transaction
        def create_family(db, name, owner_id):
            fam = Family(name=name, created_by=owner_id)
            db.add(fam)
            db.flush()                    # 要拿 fam.id 的話先 flush
            db.add(FamilyMember(family_id=fam.id, user_id=owner_id, role="parent"))
            return fam

        create_family("王家", 1)            # 自動開 session、成功 commit、失敗 rollback、最後關閉
        create_family("王家", 1, db=db)     # 已經在交易裡：用傳進來的 db，不 commit
    """

    @functools.wraps(fn)
    def wrapper(*args: Any, db: Session | None = None, **kwargs: Any) -> T:
        with session_scope(db) as s:
            return fn(s, *args, **kwargs)

    return wrapper
