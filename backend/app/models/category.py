"""
分類體系（系統預設＋家庭自訂）。

負責人：成員2（記帳）　✦ 分支：m2-ledger

===========================================================================
⚠️ 欄位的正本是 frontend/js/data.js 的 schema
===========================================================================
改欄位要三處一起改：data.js 的 schema → 這個檔案 → Alembic 遷移（alembic revision --autogenerate）。
tests/test_backend_core.py 會逐欄比對 data.js 與這裡，漏改一處就紅燈。

資料表：categories

增刪改查不用自己寫 SQL：用 app/toolkit/crud.py（find／get／save／remove）。
"""

from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models._types import BigID
from app.toolkit.db import Base


class Category(Base):
    """分類。系統預設 + 家庭自訂"""

    __tablename__ = "categories"

    # PK
    id: Mapped[int] = mapped_column(BigID, primary_key=True)
    # FK → families，NULL = 系統預設
    family_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    # 'income' / 'expense'
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    # FK → categories，支援兩層分類
    parent_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("categories.id"), nullable=True)
    color: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
