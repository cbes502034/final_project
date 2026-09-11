"""
收支明細的資料表。 ✦ 負責人：成員2（收支明細）　✦ 分支：m2-ledger

===========================================================================
這個檔案要定義哪幾張表
===========================================================================
    transactions       一筆收支。amount 用 Numeric(14,2)、source 記 nlp 或 manual
    accounts           現金／銀行／信用卡／悠遊卡。優先序 S，有時間再做

欄位定義照專題手冊「資料庫設計」那一節。

===========================================================================
怎麼寫一張表
===========================================================================
    from decimal import Decimal
    from sqlalchemy import ForeignKey, Numeric
    from sqlalchemy.orm import Mapped, mapped_column
    from app.core.database import Base

    class Example(Base):
        __tablename__ = "examples"
        id: Mapped[int] = mapped_column(primary_key=True)
        owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
        amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))

⚠️ **金額一律用 Numeric(14, 2)，絕對不要用 Float。**
浮點數累加幾千筆之後會出現 12345.670000000002，財務系統不能接受。

寫完之後要到 models/__init__.py 把它 import 進去，
Alembic 才看得到它、才產得出遷移檔。

⚠️ `source` 這一欄很重要，**不可以隨便填**：

    manual   走 POST /api/transactions，沒經過模型
    nlp      走 POST /api/nlp/confirm，經過模型並由使用者確認

兩者混在一起的話，成員4 算模型正確率時分母就錯了，整份評測報告不能看。
"""

# TODO(成員2): 定義上面列的資料表
