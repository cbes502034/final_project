"""
預算與每月存款目標。

負責人：成員3（數字）　✦ 分支：m3-analytics

===========================================================================
⚠️ 欄位的正本是 frontend/js/data.js 的 schema
===========================================================================
改欄位要三處一起改：data.js 的 schema → 這個檔案 → Alembic 遷移（alembic revision --autogenerate）。
tests/test_backend_core.py 會逐欄比對 data.js 與這裡，漏改一處就紅燈。

資料表：budgets、savings_goals

增刪改查不用自己寫 SQL：用 app/toolkit/crud.py（find／get／save／remove）。
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models._types import BigID, utcnow
from app.toolkit.db import Base


class Budget(Base):
    """預算。月與年兩種週期"""

    __tablename__ = "budgets"

    # PK
    id: Mapped[int] = mapped_column(BigID, primary_key=True)
    # FK → users，NULL = 家庭總預算
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    # FK → families
    family_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=True)
    # FK → categories，NULL = 總額預算
    category_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("categories.id"), nullable=True)
    # 'month' / 'year'
    period_type: Mapped[str] = mapped_column(Text, nullable=False, default="month")
    # '2026-09' 或 '2026'
    period_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    limit_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    # FK → users
    created_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)


class SavingsGoal(Base):
    """每月存款目標。★ 註冊後的個人化設定第一步就填。改過的值保留歷史，不覆蓋"""

    __tablename__ = "savings_goals"

    # PK
    id: Mapped[int] = mapped_column(BigID, primary_key=True)
    # FK → users
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    # FK → groups。NULL = 不分帳本的整體目標
    group_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("groups.id"), nullable=True)
    # '2026-09'。NULL = 預設值，套用到所有未指定的月份
    period_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 每月想存多少
    goal_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    # 達可支配上限的幾成時提醒，預設 0.8
    warn_ratio: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True, default=Decimal("0.8"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    # FK → users，一定是本人。存多少錢由自己決定
    created_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
