"""
稽核紀錄的資料表。 ✦ 負責人：成員4（稽核紀錄）　✦ 分支：m4-access

===========================================================================
這個檔案要定義哪幾張表
===========================================================================
    audit_logs         誰在什麼時候看了誰的資料、誰改了誰的權限

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

監管功能一旦存在，就**必須有紀錄可查**，
否則權限會變成沒人管的黑箱。優先序 S，但不要忘記它存在。
"""

# TODO(成員4): 定義上面列的資料表
