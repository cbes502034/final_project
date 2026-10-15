"""
所有資料表。import 這個套件，Base.metadata 就認得全部 20 張表（Alembic 與 create_all 都靠它）。

負責人：共用（改之前在群組講一聲）。每個檔案的主人寫在檔頭。
"""

from app.models.advice import Advice  # noqa: F401
from app.models.alert import AlertRule  # noqa: F401
from app.models.audit import AuditLog  # noqa: F401
from app.models.budget import Budget, SavingsGoal  # noqa: F401
from app.models.category import Category  # noqa: F401
from app.models.family import Family, FamilyMember, FamilyInvite  # noqa: F401
from app.models.group import Group, GroupMember  # noqa: F401
from app.models.guardianship import Guardianship, Allowance  # noqa: F401
from app.models.nlp import NlpParse  # noqa: F401
from app.models.notification import Notification  # noqa: F401
from app.models.transaction import Account, Transaction  # noqa: F401
from app.models.user import User, UserSession, PasswordReset  # noqa: F401

__all__ = ["User", "UserSession", "PasswordReset", "Family", "FamilyMember", "FamilyInvite", "Guardianship", "Allowance", "Notification", "AuditLog", "Category", "Account", "Transaction", "NlpParse", "Group", "GroupMember", "Budget", "SavingsGoal", "AlertRule", "Advice"]

#: 表名 → 模型類別。crud 與測試用
TABLES = {"users": User, "sessions": UserSession, "password_resets": PasswordReset, "families": Family, "family_members": FamilyMember, "family_invites": FamilyInvite, "guardianships": Guardianship, "allowances": Allowance, "notifications": Notification, "audit_logs": AuditLog, "categories": Category, "accounts": Account, "transactions": Transaction, "nlp_parses": NlpParse, "groups": Group, "group_members": GroupMember, "budgets": Budget, "savings_goals": SavingsGoal, "alert_rules": AlertRule, "advices": Advice}
