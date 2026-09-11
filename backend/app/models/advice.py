"""
財務建議的資料表。 ✦ 負責人：成員3（財務建議）　✦ 分支：m3-analytics

===========================================================================
這個檔案要定義哪幾張表
===========================================================================
    advices            title、body、level、basis_json、period、scope

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

⚠️ `basis_json` 存的是**後端算好的數字**，不是模型生成的。

它的用途是讓使用者**自己驗算**。看到「你這個月餐飲超支 2,400」時，
能展開看到這是根據哪些數字算出來的。
沒有依據的建議就是黑盒子，使用者不會信。
"""

# TODO(成員3): 定義上面列的資料表
