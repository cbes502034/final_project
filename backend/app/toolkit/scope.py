"""
可見範圍：把「誰的紀錄」和「哪一本帳」兩道篩選合起來。

負責人：成員4（家庭與可見範圍）

===========================================================================
一句話
===========================================================================
一筆紀錄要同時通過兩道門，你才看得到：

    1. 這筆是誰記的  → 監管關係（自己 ＋ 我監管的人）
    2. 這筆在哪本帳  → 群組成員（我在不在那個群組裡）

**兩道是獨立的，而且都要過。** 只做一道會漏：

* 只看監管關係 → 我監管的小孩在一個我沒加入的群組（例如他自己的零用帳）
  記帳，那筆會跑到我的清單上。
* 只看群組 → 同一個群組裡別人的私人紀錄我也看得到。

===========================================================================
為什麼可見範圍不看角色
===========================================================================
`master` 沒有例外。家裡權限最高不等於看得到每個人的消費明細——
前者是「管得動」，後者是「看得到」，是兩件事。

這樣做的理由是：**「誰看得到我」必須是一份可以查、可以列出來的清單。**
一旦寫成 `if role == "master": return everyone`，被監管的人就再也無法
確認自己的紀錄到底被誰看過。

===========================================================================
怎麼用
===========================================================================
    from app.toolkit import scope

    users  = scope.visible_users(me_id, guardianships)
    groups = scope.visible_groups(me_id, group_members)

    rows = (
        db.query(Transaction)
          .filter(Transaction.user_id.in_(users))
          .filter(Transaction.group_id.in_(groups))
          .all()
    )

要擋單一目標（例如 `GET /api/transactions?userId=U3`）：

    scope.require_user(target_id, users)     # 沒權限就丟 Forbidden
    scope.require_group(group_id, groups)

⚠️ **沒權限要回 403，不要回空陣列。**
回空的話，前端分不出「這個人沒記帳」和「你不能看」。
"""

from __future__ import annotations

from typing import Iterable, Protocol, Sequence

__all__ = [
    "Forbidden",
    "visible_users",
    "visible_groups",
    "can_see_user",
    "can_see_group",
    "require_user",
    "require_group",
    "filter_rows",
]


class Forbidden(PermissionError):
    """要看的東西不在可見範圍內。路由層把它轉成 403。"""


class _Guardianship(Protocol):
    """只要有這兩個屬性就能用——ORM 物件、dataclass、具名元組都行。"""

    guardian_id: object
    ward_id: object


class _GroupMember(Protocol):
    group_id: object
    user_id: object


def _attr(obj: object, *names: str) -> object:
    """容忍幾種命名：guardian_id / guardian、ward_id / ward。

    mock 用的是短名，ORM 用的是 _id 結尾，測試不該為了這個寫兩套。
    """
    for n in names:
        if isinstance(obj, dict) and n in obj:
            return obj[n]
        if hasattr(obj, n):
            return getattr(obj, n)
    raise AttributeError(f"{obj!r} 沒有 {' / '.join(names)} 任何一個欄位")


def visible_users(me: object, guardianships: Iterable[object]) -> set:
    """我看得到誰的紀錄：自己 ＋ 我監管的人。

    ⚠️ 只算還有效的監管關係。已經解除的（`ended_at` 有值）要先濾掉，
    這裡不幫你濾——查資料庫時就該加 `WHERE ended_at IS NULL`，
    不要把整張表撈出來再用 Python 過濾。

    >>> visible_users("U1", [{"guardian_id": "U1", "ward_id": "U3"},
    ...                      {"guardian_id": "U2", "ward_id": "U4"}]) == {"U1", "U3"}
    True
    >>> visible_users("U3", []) == {"U3"}
    True
    """
    out = {me}
    for g in guardianships:
        if _attr(g, "guardian_id", "guardian") == me:
            out.add(_attr(g, "ward_id", "ward"))
    return out


def visible_groups(me: object, group_members: Iterable[object]) -> set:
    """我看得到哪幾本帳：我有加入的群組。

    >>> visible_groups("U1", [{"group_id": "G1", "user_id": "U1"},
    ...                       {"group_id": "G2", "user_id": "U2"}]) == {"G1"}
    True
    """
    return {
        _attr(m, "group_id", "group")
        for m in group_members
        if _attr(m, "user_id", "user") == me
    }


def can_see_user(target: object, users: Iterable[object]) -> bool:
    return target in set(users)


def can_see_group(group: object, groups: Iterable[object]) -> bool:
    return group in set(groups)


def require_user(target: object, users: Iterable[object]) -> None:
    """不在可見範圍就丟 Forbidden。路由層轉成 403。"""
    if not can_see_user(target, users):
        raise Forbidden("你沒有權限看這個人的紀錄")


def require_group(group: object, groups: Iterable[object]) -> None:
    if not can_see_group(group, groups):
        raise Forbidden("你不在這個群組裡")


def filter_rows(
    rows: Sequence[object],
    users: Iterable[object],
    groups: Iterable[object],
) -> list:
    """兩道篩選都套上。

    這是給「已經在記憶體裡的資料」用的（例如測試、或算統計時的中間結果）。
    ⚠️ 正式查詢請把條件下到 SQL 的 WHERE，不要整張表撈出來再篩——
    資料一多就是全表掃描。

    >>> rows = [{"user_id": "U3", "group_id": "G1"},
    ...         {"user_id": "U3", "group_id": "G3"},
    ...         {"user_id": "U2", "group_id": "G1"}]
    >>> filter_rows(rows, {"U1", "U3"}, {"G1"})
    [{'user_id': 'U3', 'group_id': 'G1'}]
    """
    us, gs = set(users), set(groups)
    return [
        r
        for r in rows
        if _attr(r, "user_id", "user") in us and _attr(r, "group_id", "group") in gs
    ]
