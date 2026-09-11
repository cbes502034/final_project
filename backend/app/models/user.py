"""
帳號的資料表。 ✦ 負責人：成員1（帳號）　✦ 分支：m1-auth

===========================================================================
這個檔案要定義哪幾張表
===========================================================================
    users              登入身分。email、password_hash、display_name、birth_year
    sessions           refresh token 的雜湊、到期時間、revoked_at

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

⚠️ users 存的是**登入身分**，不是家庭角色。
一個人可以同時是甲家的管理者、乙家的成員，所以角色在成員4 的
family_members 表。這兩張表刻意分開，不要合併。

⚠️ sessions 存的是 refresh token 的**雜湊值，不是原文**。
道理跟密碼一樣：資料庫外洩時攻擊者拿到原文就能直接冒用登入。
"""

# TODO(成員1): 定義上面列的資料表
