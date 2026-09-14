"""
路由。一組一個檔案，由 app/main.py 用 include_router 掛上（prefix 一律是 /api）。

負責人：共用。每個檔案的主人寫在檔頭；誰負責哪一支看 app/ownership.py。
"""

from app.routers import (  # noqa: F401
    admin, advices, alerts, auth, budgets, categories, family, groups, nlp, notifications, stats, transactions,
)

#: main.py 依序掛上
ALL = [auth, admin, transactions, nlp, categories, groups, stats, budgets, alerts, advices, family, notifications]
