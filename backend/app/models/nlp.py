"""
模型解析紀錄的資料表。 ✦ 負責人：成員2（模型解析紀錄）　✦ 分支：m2-ledger

===========================================================================
這個檔案要定義哪幾張表
===========================================================================
    nlp_parses         ★ 原始輸入、模型輸出、使用者修正值、模型版本、parse_id

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

★ **這張表是本系統最值錢的東西。**

使用者每修正一次解析結果，就等於免費標了一筆訓練資料。
這張表同時是：

    成員4 算模型正確率的**評測來源**
    下一輪 few-shot / 微調的**訓練資料**

所以 `user_corrected` 這一欄一定要存，而且要能分辨
「使用者沒改」和「使用者改成空值」——用 NULL 和空字串區分。
"""

# TODO(成員2): 定義上面列的資料表
