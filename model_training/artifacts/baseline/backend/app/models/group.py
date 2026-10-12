"""
帳本與帳本成員。

負責人：成員2（記帳）　✦ 分支：m2-ledger

===========================================================================
⚠️ 欄位的正本是 frontend/js/data.js 的 schema
===========================================================================
改欄位要三處一起改：data.js 的 schema → 這個檔案 → Alembic 遷移（alembic revision --autogenerate）。
tests/test_backend_core.py 會逐欄比對 data.js 與這裡，漏改一處就紅燈。

資料表：groups、group_members

增刪改查不用自己寫 SQL：用 app/toolkit/crud.py（find／get／save／remove）。
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models._types import BigID, utcnow
from app.toolkit.db import Base


class Group(Base):
    """帳本。★ 一個家庭可以開好幾本帳，各自有自己的存款目標"""

    __tablename__ = "groups"

    # PK
    id: Mapped[int] = mapped_column(BigID, primary_key=True)
    # FK → families
    family_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=True)
    # 例如「家用」「旅遊基金」
    name: Mapped[str] = mapped_column(Text, nullable=False)
    # 圖表與標籤的顏色
    color: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 這本帳是做什麼的，建立的人寫
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # FK → users
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    # NULL = 使用中。封存不刪除，舊紀錄要留著
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 'standing' 常設 / 'temp' 臨時（有結束日、會結算）
    kind: Mapped[str] = mapped_column(Text, nullable=False, default="standing")
    # 臨時帳本的結束日。常設為 NULL
    ends_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    # NULL = 還沒結算。結算後這本帳唯讀
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # NULL = 還在。只有結算過的才能移除；移除不能復原，紀錄一筆都不刪
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class GroupMember(Base):
    """帳本成員。可見範圍的另一條路：我在這本帳裡就看得到這本帳"""

    __tablename__ = "group_members"

    # PK, FK → groups
    group_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("groups.id"), primary_key=True)
    # PK, FK → users
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), primary_key=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    # 這本帳有動靜要不要通知我。預設 false
    notify: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
