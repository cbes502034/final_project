"""
路由。**一個領域一個資料夾，一個人一個資料夾**：

    auth/       成員1 · 認證     分支 m1-auth       auth.py、admin.py
    ledger/     成員2 · 記帳     分支 m2-ledger     transactions.py、nlp.py、categories.py、groups.py
    analytics/  成員3 · 數字     分支 m3-analytics  stats.py、budgets.py、alerts.py、advices.py
    access/     成員4 · 家庭     分支 m4-access     family.py、notifications.py

開自己的資料夾，裡面的東西都是你的；別人的資料夾不要動。
誰負責哪一支路由看 app/ownership.py（唯一的事實來源），或跑 `python -m app.ownership`。

⚠️ models/ 與 schemas/ **沒有**跟著分資料夾：那兩層的 __init__.py 是共用的，
   而且 models 之間有 SQLAlchemy 的 relationship 互相 import、alembic 也要一次看得到全部。
   哪個檔案是誰的一樣寫在 ownership.py 與各檔案的檔頭。

負責人：共用（這個檔案與 _stub.py）。新增一組路由才會動到這裡，改之前先在群組講一聲。
"""

from app.routers.access import family, notifications  # noqa: F401
from app.routers.analytics import advices, alerts, budgets, stats  # noqa: F401
from app.routers.auth import admin, auth  # noqa: F401
from app.routers.ledger import categories, groups, nlp, transactions  # noqa: F401

#: main.py 依序掛上（prefix 一律是 /api）
ALL = [auth, admin, transactions, nlp, categories, groups, stats, budgets, alerts, advices, family, notifications]
