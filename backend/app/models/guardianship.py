"""
監管關係與零用金。

負責人：成員4（家庭）　✦ 分支：m4-access

===========================================================================
⚠️ 欄位的正本是 frontend/js/data.js 的 schema
===========================================================================
改欄位要三處一起改：data.js 的 schema → 這個檔案 → Alembic 遷移（alembic revision --autogenerate）。
tests/test_backend_core.py 會逐欄比對 data.js 與這裡，漏改一處就紅燈。

資料表：guardianships、allowances

增刪改查不用自己寫 SQL：用 app/toolkit/crud.py（find／get／save／remove）。
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models._types import BigID, utcnow
from app.toolkit.db import Base


class Guardianship(Base):
    """監管關係。誰看得到誰的明細。雙方都看得到這張表"""

    __tablename__ = "guardianships"

    # PK
    id: Mapped[int] = mapped_column(BigID, primary_key=True)
    # FK → users
    guardian_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    # FK → users
    ward_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    # 'all' / 'summary_only'
    scope: Mapped[str] = mapped_column(Text, nullable=False, default="全部明細")
    # FK → users，只有家長能建立
    created_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    since: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Allowance(Base):
    """每月零用金。★ 設定，不是支出紀錄。家長每月給某個被監管者多少"""

    __tablename__ = "allowances"

    # PK
    id: Mapped[int] = mapped_column(BigID, primary_key=True)
    # FK → users，給錢的人
    payer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    # FK → users，收錢的人
    ward_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    # 每月金額
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    # '2026-09'。NULL = 預設值，套用到未指定的月份
    period_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
