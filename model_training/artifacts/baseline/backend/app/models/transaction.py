"""
收支明細與帳戶。

負責人：成員2（記帳）　✦ 分支：m2-ledger

===========================================================================
⚠️ 欄位的正本是 frontend/js/data.js 的 schema
===========================================================================
改欄位要三處一起改：data.js 的 schema → 這個檔案 → Alembic 遷移（alembic revision --autogenerate）。
tests/test_backend_core.py 會逐欄比對 data.js 與這裡，漏改一處就紅燈。

資料表：accounts、transactions

增刪改查不用自己寫 SQL：用 app/toolkit/crud.py（find／get／save／remove）。
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models._types import BigID, utcnow
from app.toolkit.db import Base


class Account(Base):
    """帳戶／錢包。現金、銀行、悠遊卡、信用卡"""

    __tablename__ = "accounts"

    # PK
    id: Mapped[int] = mapped_column(BigID, primary_key=True)
    # FK → users
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    # 'cash' / 'bank' / 'card' / 'ecard'
    kind: Mapped[str | None] = mapped_column(Text, nullable=True)
    balance: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Transaction(Base):
    """收支明細。核心表。所有統計都從這裡算"""

    __tablename__ = "transactions"

    # PK
    id: Mapped[int] = mapped_column(BigID, primary_key=True)
    # FK → users
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    # FK → groups，這筆算在哪一本帳上。INDEX
    group_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("groups.id"), nullable=False, index=True)
    # FK → families，INDEX
    family_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=True, index=True)
    # FK → accounts
    account_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("accounts.id"), nullable=True)
    # FK → categories
    category_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("categories.id"), nullable=False)
    # 'income' / 'expense' / 'transfer'。⚠️ transfer 不進任何收支加總
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    # 一律正數，方向看 kind
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    # INDEX，統計用
    occurred_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    merchant: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 'manual' / 'nlp' / 'import'
    source: Mapped[str] = mapped_column(Text, nullable=False, default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
