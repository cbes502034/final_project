"""
家庭與權限的資料表。 ✦ 負責人：成員4（家庭與權限）　✦ 分支：m4-access

===========================================================================
這個檔案要定義哪幾張表
===========================================================================
    families           家庭。name、created_by
    family_members     ★ 家庭角色。master / parent / member、status
    guardianships      ★ 監管關係。guardian_id、ward_id、ended_at
    family_invites     邀請碼。code、expires_at、used_at

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

⚠️ **刪除一律用標記，不要真的 DELETE。**

    移除成員    family_members.status = 'removed'
    解除監管    guardianships.ended_at = 現在

理由：那個人過去記的帳還在，直接刪掉會讓歷史統計整個對不上；
而且稽核需要看得到「誰在什麼時候被移除」。

⚠️ `guardianships` 是**雙向可見**的。被監管者自己也查得到誰在監管他。
這不是漏洞，是刻意的設計 —— 系統不提供「隱藏監管」的選項。
"""

# TODO(成員4): 定義上面列的資料表
