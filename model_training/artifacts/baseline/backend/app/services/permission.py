"""
可見範圍：這個人看得到誰、看得到哪幾本帳。**規則本身在 toolkit/scope.py，這裡只負責去資料庫拿資料餵進去。**

負責人：成員4（家庭）　✦ 分支：m4-access（共用元件：每一支查明細、統計的路由都會用）

已經可以直接用：
    users, groups = visible(me, db)
    rows = crud.find(Transaction, {"or": [{"user_id__in": users}, {"group_id__in": groups}]})
    ⚠️ 一定是 or（監管 ∪ 同帳本），寫成兩個條件 AND 就變回交集了
"""

from __future__ import annotations

from typing import Any

from app.guards import visible_scope


def visible(me: Any, db: Any) -> tuple[set, set]:
    """(我看得到的人, 我看得到的帳本)。平台管理員兩個都是空的——他讀不到任何帳。"""
    if getattr(me, "is_platform_admin", False):
        return set(), set()
    return visible_scope(me, db)
