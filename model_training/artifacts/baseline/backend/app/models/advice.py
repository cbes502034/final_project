"""
LLM 財務建議。

負責人：成員3（數字）　✦ 分支：m3-analytics

===========================================================================
⚠️ 欄位的正本是 frontend/js/data.js 的 schema
===========================================================================
改欄位要三處一起改：data.js 的 schema → 這個檔案 → Alembic 遷移（alembic revision --autogenerate）。
tests/test_backend_core.py 會逐欄比對 data.js 與這裡，漏改一處就紅燈。

資料表：advices

增刪改查不用自己寫 SQL：用 app/toolkit/crud.py（find／get／save／remove）。
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models._types import BigID, JSONType, utcnow
from app.toolkit.db import Base


class Advice(Base):
    """LLM 財務建議。使用者按「產生建議」時寫一列，附依據。同一個月、同一個範圍再產生會蓋掉舊的"""

    __tablename__ = "advices"

    # PK
    id: Mapped[int] = mapped_column(BigID, primary_key=True)
    # FK → families
    family_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=True)
    # FK → users，NULL = 家庭層級建議
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    # 'month' / 'year'
    period_type: Mapped[str] = mapped_column(Text, nullable=False, default="month")
    period_key: Mapped[str] = mapped_column(Text, nullable=False)
    # 'ok' / 'info' / 'warn'
    level: Mapped[str] = mapped_column(Text, nullable=False)
    # LLM 生成
    title: Mapped[str] = mapped_column(Text, nullable=False)
    # LLM 生成
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # ★ 依據的數字，由後端計算後餵給模型
    basis_json: Mapped[Any | None] = mapped_column(JSONType, nullable=True)
    # LLM 生成
    suggestions_json: Mapped[Any | None] = mapped_column(JSONType, nullable=True)
    # 模型對這則的信心，0～1
    confidence: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    model_ver: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
