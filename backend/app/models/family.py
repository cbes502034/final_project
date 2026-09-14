"""
家庭、家庭成員與角色、邀請與邀請碼。

負責人：成員4（家庭）　✦ 分支：m4-access

===========================================================================
⚠️ 欄位的正本是 frontend/js/data.js 的 schema
===========================================================================
改欄位要三處一起改：data.js 的 schema → 這個檔案 → Alembic 遷移（alembic revision --autogenerate）。
tests/test_backend_core.py 會逐欄比對 data.js 與這裡，漏改一處就紅燈。

資料表：families、family_members、family_invites

增刪改查不用自己寫 SQL：用 app/toolkit/crud.py（find／get／save／remove）。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models._types import BigID, utcnow
from app.toolkit.db import Base


class Family(Base):
    """家庭。一個家庭一列"""

    __tablename__ = "families"

    # PK
    id: Mapped[int] = mapped_column(BigID, primary_key=True)
    # 例如「林家」
    name: Mapped[str] = mapped_column(Text, nullable=False)
    # FK → users，開這個家的人。⚠️ 僅供稽核，不給任何額外權限
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    # 預設 'TWD'
    currency: Mapped[str] = mapped_column(Text, nullable=False, default="TWD")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class FamilyMember(Base):
    """家庭成員與角色。一個人同時只屬於一個家庭"""

    __tablename__ = "family_members"

    # PK, FK → families
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), primary_key=True)
    # PK, FK → users。UNIQUE：一個人只能在一個家庭
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), primary_key=True, unique=True)
    # 'parent' / 'child'。家長之間互相看得到；看子女要有監管關係
    role: Mapped[str] = mapped_column(Text, nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    # 'active' / 'removed'
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")


class FamilyInvite(Base):
    """家庭邀請。★ 邀請碼與用帳號邀請都記在這裡"""

    __tablename__ = "family_invites"

    # PK
    id: Mapped[int] = mapped_column(BigID, primary_key=True)
    # FK → families
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False)
    # FK → users，發出邀請的家長
    inviter_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    # FK → users。用邀請碼時為 NULL，有人拿碼加入才填
    invitee_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    # 邀請碼的雜湊，只有邀請碼才有。⚠️ 不存明碼
    code_hash: Mapped[str | None] = mapped_column(Text, nullable=True, unique=True)
    # 'parent' / 'child'，由家長決定，被邀請的人不能改
    role: Mapped[str] = mapped_column(Text, nullable=False)
    # 'pending' / 'accepted' / 'declined' / 'cancelled'
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    # 七天後過期
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
