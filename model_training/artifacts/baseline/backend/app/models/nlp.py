"""
自然語言解析紀錄（模型評測的資料來源）。

負責人：成員2（記帳）　✦ 分支：m2-ledger

===========================================================================
⚠️ 欄位的正本是 frontend/js/data.js 的 schema
===========================================================================
改欄位要三處一起改：data.js 的 schema → 這個檔案 → Alembic 遷移（alembic revision --autogenerate）。
tests/test_backend_core.py 會逐欄比對 data.js 與這裡，漏改一處就紅燈。

資料表：nlp_parses

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


class NlpParse(Base):
    """自然語言記帳解析紀錄。★ 這是 LLM 評測的資料來源"""

    __tablename__ = "nlp_parses"

    # PK
    id: Mapped[int] = mapped_column(BigID, primary_key=True)
    # FK → transactions，NULL = 使用者放棄
    transaction_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("transactions.id"), nullable=True)
    # FK → users
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    # 使用者原始輸入
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    # 模型輸出的結構化結果
    parsed_json: Mapped[Any | None] = mapped_column(JSONType, nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    cat_confidence: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    # 使用者修正後的值，NULL = 未修正
    user_corrected: Mapped[Any | None] = mapped_column(JSONType, nullable=True)
    # 換模型要能分開比較
    model_ver: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
