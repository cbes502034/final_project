"""
平台管理頁要看的兩張表：安全事件、錯誤紀錄。

領域：認證

===========================================================================
⚠️ 欄位的正本是 frontend/js/data.js 的 schema
===========================================================================
改欄位要三處一起改：data.js 的 schema → 這個檔案 → Alembic 遷移（alembic revision --autogenerate）。
tests/test_backend_core.py 會逐欄比對 data.js 與這裡，漏改一處就紅燈。

資料表：security_events、error_logs

⚠️ 兩張表都**不放任何財務內容**：沒有金額、沒有備註、沒有記帳的那句話。
   平台管理員看得到這兩張表，放進來就等於開了一條看帳的後門。
寫入一律走 app/toolkit/security.py（record、log_error），不要在路由裡直接 crud.save。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models._types import BigID, utcnow
from app.toolkit.db import Base


class SecurityEvent(Base):
    """安全事件。登入失敗、被規則擋下的請求、AI 用量。平台管理頁的「安全事件」讀它"""

    __tablename__ = "security_events"

    # PK
    id: Mapped[int] = mapped_column(BigID, primary_key=True)
    # 'login_failed' / 'login_locked' / 'ai_quota' …（toolkit/security.py 的 KINDS）
    kind: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    # FK → users。查不到是誰時是 NULL
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True, index=True)
    # 登入用的 email 的雜湊。帳號不存在也照樣算次數，不然鎖不鎖就洩漏了帳號在不在
    subject: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    # 來源 IP 的雜湊，只拿來數次數
    ip_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 給管理員看的一句話。⚠️ 不放密碼、金額、記帳內容
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)


class ErrorLog(Base):
    """錯誤紀錄。後端沒接住的錯誤、使用者畫面上出的錯。平台管理頁即時顯示"""

    __tablename__ = "error_logs"

    # PK
    id: Mapped[int] = mapped_column(BigID, primary_key=True)
    # 'server' 後端／'client' 使用者的瀏覽器
    source: Mapped[str] = mapped_column(Text, nullable=False)
    # HTTP 狀態碼。畫面程式出錯是 NULL
    status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    method: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 出錯的路由或畫面（#/entry）。不含查詢參數
    path: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 出錯的函式或例外類型。只給管理員看，使用者畫面上不出現
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 最多 300 字。⚠️ 不放請求內容（金額、備註）
    message: Mapped[str] = mapped_column(Text, nullable=False)
    # FK → users。沒登入時是 NULL
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)
