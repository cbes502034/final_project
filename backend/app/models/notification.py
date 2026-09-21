"""
通知（監管對象記帳、跨過提醒門檻）。

負責人：成員4（家庭）　✦ 分支：m4-access

===========================================================================
⚠️ 欄位的正本是 frontend/js/data.js 的 schema
===========================================================================
改欄位要三處一起改：data.js 的 schema → 這個檔案 → Alembic 遷移（alembic revision --autogenerate）。
tests/test_backend_core.py 會逐欄比對 data.js 與這裡，漏改一處就紅燈。

資料表：notifications

增刪改查不用自己寫 SQL：用 app/toolkit/crud.py（find／get／save／remove）。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models._types import BigID, JSONType, utcnow
from app.toolkit.db import Base


class Notification(Base):
    """通知。★ 監管對象記帳、或支出跨過提醒門檻時寫一列"""

    __tablename__ = "notifications"
    __table_args__ = (UniqueConstraint("recipient_id", "transaction_id", name="uq_notification_once"), Index("ix_notifications_recipient_created", "recipient_id", "created_at"),)

    # PK
    id: Mapped[int] = mapped_column(BigID, primary_key=True)
    # FK → users，收件人。查詢一律 WHERE recipient_id = 我
    recipient_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    # FK → users，做這件事的人。系統發的為 NULL
    actor_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    # 'ward_transaction'（監管對象記帳）/ 'group_transaction'（帳本有開通知）/ 'budget_alert'（跨過提醒門檻）
    type: Mapped[str] = mapped_column(Text, nullable=False)
    # FK → transactions，非記帳類通知為 NULL。⚠️ UNIQUE (recipient_id, transaction_id)：同一筆對同一個人只發一則
    transaction_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("transactions.id"), nullable=True)
    # 提醒類通知放門檻百分比、帳本、金額
    payload_json: Mapped[Any | None] = mapped_column(JSONType, nullable=True)
    # NULL = 未讀。紅點數字就是數這個
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 與 recipient_id 做複合索引，輪詢查得快
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
