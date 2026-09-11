"""
預算與存款目標的資料表。 ✦ 負責人：成員3（預算與存款目標）　✦ 分支：m3-analytics

===========================================================================
這個檔案要定義哪幾張表
===========================================================================
    categories         分類體系。系統預設 + 家庭自訂，支援兩層
    budgets            各分類的月預算上限
    savings_goals      ★ 每月存款目標。帶 period_key

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

⚠️ `savings_goals` 改動要**新增一筆，不要覆蓋舊的**。

使用者九月把目標從 20000 改成 15000 時，新增一筆 period_key='2026-09' 的紀錄。
為什麼？因為十月回頭看九月的達成狀況時，要知道**當時的目標是多少**。
每次覆蓋的話歷史就不見了，你會用現在的目標去評斷過去的表現。

⚠️ `categories` 是**第 1 週唯一要凍結的跨模組契約**。
成員2 的 prompt、成員4 的評測都要用它。定好就不要再動。
"""

# TODO(成員3): 定義上面列的資料表
