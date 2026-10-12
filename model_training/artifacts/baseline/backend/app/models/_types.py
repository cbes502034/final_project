"""
資料表共用的型別。PostgreSQL 與 SQLite 各用各的最佳型別，模型只寫一次。

負責人：成員1（共用元件）
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, BigInteger, Integer
from sqlalchemy.dialects.postgresql import JSONB

#: BIGSERIAL 主鍵。SQLite 只有 INTEGER PRIMARY KEY 會自動遞增，所以在 SQLite 上換成 Integer
BigID = BigInteger().with_variant(Integer(), "sqlite")

#: JSONB。PostgreSQL 用 JSONB（可以建索引、查欄位），其他資料庫退回一般 JSON
JSONType = JSON().with_variant(JSONB(), "postgresql")


def utcnow() -> datetime:
    """寫入時間一律存 UTC（TIMESTAMPTZ）。顯示成台灣時間是前端的事。"""
    return datetime.now(timezone.utc)
