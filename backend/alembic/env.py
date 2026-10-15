"""
Alembic 的進入點：告訴它「連哪顆資料庫」「要跟哪些表比對」。

負責人：成員1（共用元件）。一般不需要改這個檔案。

- 連線網址：讀 app/toolkit/config.py 的 DATABASE_URL（跟 FastAPI 同一份設定，密碼不進 repo）。
  臨時要對別顆資料庫跑：alembic -x url=sqlite:///./dev.db upgrade head
- 比對對象：app/models/ 的所有表（import app.models 之後 Base.metadata 就認得 20 張）。
- SQLite 不支援大部分 ALTER TABLE，所以在 SQLite 上用 batch 模式（複製一張新表再換掉）。
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config

# -x url=... 要在 import app 之前放進環境變數：app.toolkit.db 一 import 就會讀 DATABASE_URL
_OVERRIDE = context.get_x_argument(as_dictionary=True).get("url")
if _OVERRIDE:
    os.environ["DATABASE_URL"] = _OVERRIDE

import app.models  # noqa: E402,F401  ← 一定要 import，Base.metadata 才有表
from app.toolkit.config import settings  # noqa: E402
from app.toolkit.db import Base  # noqa: E402

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _url() -> str:
    """-x url=... 優先；沒給就用 DATABASE_URL。"""
    return _OVERRIDE or settings.database_url


def _options(url: str) -> dict:
    return {
        "target_metadata": target_metadata,
        "compare_type": True,                      # 欄位型別改了也要抓到
        "render_as_batch": url.startswith("sqlite"),
    }


def run_migrations_offline() -> None:
    """alembic upgrade head --sql：不連線，只印出 SQL（給要先審 SQL 的人）。"""
    url = _url()
    context.configure(url=url, literal_binds=True, dialect_opts={"paramstyle": "named"}, **_options(url))
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = _url()
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = url
    connectable = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, **_options(url))
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
