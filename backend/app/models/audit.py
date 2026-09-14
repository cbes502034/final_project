"""
稽核紀錄。

負責人：成員4（家庭）　✦ 分支：m4-access

===========================================================================
⚠️ 欄位的正本是 frontend/js/data.js 的 schema
===========================================================================
改欄位要三處一起改：data.js 的 schema → 這個檔案 → Alembic 遷移（alembic revision --autogenerate）。
tests/test_backend_core.py 會逐欄比對 data.js 與這裡，漏改一處就紅燈。

資料表：audit_logs

增刪改查不用自己寫 SQL：用 app/toolkit/crud.py（find／get／save／remove）。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models._types import BigID, JSONType, utcnow
from app.toolkit.db import Base


class AuditLog(Base):
    """稽核紀錄。誰看了誰的資料、誰改了權限"""

    __tablename__ = "audit_logs"

    # PK
    id: Mapped[int] = mapped_column(BigID, primary_key=True)
    # FK → users
    actor_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    # 'view_ward' / 'grant_guardianship' / 'change_role' …
    action: Mapped[str] = mapped_column(Text, nullable=False)
    target_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    meta_json: Mapped[Any | None] = mapped_column(JSONType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
