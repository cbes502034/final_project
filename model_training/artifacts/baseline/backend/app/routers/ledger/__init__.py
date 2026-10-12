"""成員2 · 記帳的路由

負責人：成員2（分支 m2-ledger）

這個資料夾裡的檔案**只有你會動**：
    transactions.py、nlp.py、categories.py、groups.py

共用的東西不在這裡，在上一層：
    app/routers/_stub.py       @stub 與 not_ready()（成員1 維護）
    app/routers/__init__.py    main.py 掛路由用的清單

⚠️ 新增一個路由檔案的話，要同時加進上一層的 __init__.py 的 ALL，
   並在 app/ownership.py 認領它，否則 pytest 會紅燈。
"""

from app.routers.ledger import (  # noqa: F401
    transactions, nlp, categories, groups,
)
