"""
登入身分、登入工作階段、忘記密碼的重設連結。

負責人：成員1（認證）　✦ 分支：m1-auth

===========================================================================
⚠️ 欄位的正本是 frontend/js/data.js 的 schema
===========================================================================
改欄位要三處一起改：data.js 的 schema → 這個檔案 → Alembic 遷移（alembic revision --autogenerate）。
tests/test_backend_core.py 會逐欄比對 data.js 與這裡，漏改一處就紅燈。

資料表：users、sessions、password_resets

增刪改查不用自己寫 SQL：用 app/toolkit/crud.py（find／get／save／remove）。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, LargeBinary, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models._types import BigID, JSONType, utcnow
from app.toolkit.db import Base


class User(Base):
    """使用者帳號。登入身分，與家庭角色分開"""

    __tablename__ = "users"

    # PK
    id: Mapped[int] = mapped_column(BigID, primary_key=True)
    # UNIQUE
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    # bcrypt / argon2，絕不存明碼
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    # 個人資料。⚠️ 不參與任何權限判斷
    birth_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 介面主題，預設 'paper'。只影響外觀，存在帳號上換裝置也一樣
    theme: Mapped[str] = mapped_column(Text, nullable=False, default="paper")
    # 平台管理員。與家庭角色無關，且看不到任何財務資料
    is_platform_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # NULL = 正常。⚠️ 停權只擋登入與寫入，不刪任何資料
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 停權理由。沒有理由的停權就是任意封鎖
    suspended_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # NULL = 還沒走完註冊後的個人化設定（存款目標、理財習慣、主題），登入後先帶去設定
    onboarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 大頭貼（前端已縮到 256×256）。⚠️ 存資料庫不存檔案：Render 的磁碟重新部署就清空
    avatar_bytes: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    # image/jpeg／png／webp。用 toolkit/images.py 驗過的真實格式，不信副檔名
    avatar_mime: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 理財風格 id：safe／balanced／growth
    finance_style: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 目前最在意的 id 陣列，只收清單裡有的
    finance_goals: Mapped[Any | None] = mapped_column(JSONType, nullable=True)
    # 固定的財務安排 id 陣列
    finance_habits: Mapped[Any | None] = mapped_column(JSONType, nullable=True)
    # 補充說明，最多 200 字。⚠️ 組 prompt 時標示成資料，不是指令（toolkit/profile.py）
    finance_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UserSession(Base):
    """登入工作階段。支援登出與強制下線"""

    __tablename__ = "sessions"

    # PK
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # FK → users
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    # 只存雜湊
    refresh_token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # NULL = 仍有效
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 最近一次用這張 refresh token 的時間。「登入中的裝置」要顯示
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PasswordReset(Base):
    """重設密碼連結。忘記密碼寄出的一次性連結。30 分鐘失效、只能用一次"""

    __tablename__ = "password_resets"

    # PK
    id: Mapped[int] = mapped_column(BigID, primary_key=True)
    # FK → users
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    # UNIQUE。只存雜湊，信裡的 token 原文不進資料庫
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    # 建立後 30 分鐘
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # NULL = 還沒用過。用過就作廢，並撤銷這個人所有的 sessions
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 重寄冷卻用：同一個人 60 秒內不再寄
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
