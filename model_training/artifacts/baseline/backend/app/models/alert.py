"""
階段性提醒的門檻。

負責人：成員3（數字）　✦ 分支：m3-analytics

===========================================================================
⚠️ 欄位的正本是 frontend/js/data.js 的 schema
===========================================================================
改欄位要三處一起改：data.js 的 schema → 這個檔案 → Alembic 遷移（alembic revision --autogenerate）。
tests/test_backend_core.py 會逐欄比對 data.js 與這裡，漏改一處就紅燈。

資料表：alert_rules

增刪改查不用自己寫 SQL：用 app/toolkit/crud.py（find／get／save／remove）。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models._types import BigID, utcnow
from app.toolkit.db import Base


class AlertRule(Base):
    """階段性提醒門檻。★ 使用者自己設幾個百分比，跨過就通知"""

    __tablename__ = "alert_rules"
    __table_args__ = (UniqueConstraint("user_id", "group_id", "percent", name="uq_alert_rule"),)

    # PK
    id: Mapped[int] = mapped_column(BigID, primary_key=True)
    # FK → users
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    # FK → groups。NULL = 針對整體目標
    group_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("groups.id"), nullable=True)
    # 支出佔可支配上限的百分比，1~200
    percent: Mapped[int] = mapped_column(Integer, nullable=False)
    # 關掉但不刪除，使用者常常只是暫時不想被吵
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # '2026-09'。⚠️ 同一個門檻一個月只響一次，靠這欄擋
    fired_period: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
