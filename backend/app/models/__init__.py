"""
SQLAlchemy 資料表定義（13 張）。一個檔案一個主人。

    檔案             主人     資料表
    ---------------------------------------------------------------
    user.py          成員1    users, sessions
    family.py        成員4    families, family_members, guardianships, family_invites
    audit.py         成員4    audit_logs
    transaction.py   成員2    transactions, accounts
    nlp.py           成員2    nlp_parses ★ 資料飛輪
    budget.py        成員3    categories, budgets, savings_goals
    advice.py        成員3    advices

**只改自己那個檔案。** 需要引用別人的表（例如外鍵指到 users.id）時，
用字串形式 ForeignKey("users.id") 就好，不必 import 對方的類別，
這樣兩個人就不會因為 import 順序打架。

下面的 import 是為了讓 Alembic 看得到所有表。
新增資料表檔案時要記得補一行 —— 這是少數需要動到共用檔案的時候。
"""

# TODO(全員): 各自的 models 寫好之後，把對應的 import 解除註解
# from app.models.user import User, Session          # 成員1
# from app.models.family import Family, FamilyMember, Guardianship  # 成員4
# from app.models.audit import AuditLog              # 成員4
# from app.models.transaction import Transaction, Account          # 成員2
# from app.models.nlp import NlpParse                # 成員2
# from app.models.budget import Category, Budget, SavingsGoal      # 成員3
# from app.models.advice import Advice               # 成員3
