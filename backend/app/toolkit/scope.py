"""
可見範圍：看得到一筆紀錄的兩條路。

負責人：成員4（家庭與可見範圍）

===========================================================================
一句話
===========================================================================
一筆紀錄只要通過**其中一條**，你就看得到：

    A. 這筆是誰記的  → 我自己，或我監管的人（**跨所有帳本，無條件**）
    B. 這筆在哪本帳  → 我有加入的帳本（那本帳的成員彼此看得到）

**兩條是聯集，不是交集。** 兩者各自回答一個不同的問題：

* A 是**監管**。家長對子女的可見度不該被帳本切斷——否則子女只要另外
  開一本不加家長的帳，就完全躲開了監管。鎖住「離開群組」也堵不住，
  因為他根本不用離開，另外開一本就好。
* B 是**分享**。把誰加進帳本，就是選擇讓他看到那本帳——這是記帳的人
  自己的行為，不需要誰核准。

⚠️ 早期版本用的是交集（兩道都要過），那是錯的：它讓監管有一個
   一鍵可繞的破口，同時又讓「把人加進帳本」什麼也不代表。

===========================================================================
為什麼可見範圍不看角色
===========================================================================
**家長沒有例外。** 是家長不等於看得到每個人的消費明細——
前者是「管得動」，後者是「看得到」，是兩件事。角色管的是治理動作
（邀請成員、設家庭預算），那些寫在 `app.toolkit.roles`。

這樣做的理由是：**「誰看得到我」必須是一份可以查、可以列出來的清單。**
一旦寫成 `if role == "parent": return everyone`，被監管的人就再也無法
確認自己的紀錄到底被誰看過。

**平台管理員（master）更是完全看不到。** 他能停權，但讀不到任何一筆帳——
停權是關門，不是配鑰匙。一個能讀全系統消費明細的帳號，
比家長越權嚴重得多，因為沒有任何人看得見那個視角。

===========================================================================
怎麼用
===========================================================================
    from app.toolkit import scope

    users  = scope.visible_users(me_id, guardianships)
    groups = scope.visible_groups(me_id, group_members)

    rows = (
        db.query(Transaction)
          .filter(or_(                       # ⚠️ or_，不是兩個 filter
              Transaction.user_id.in_(users),
              Transaction.group_id.in_(groups),
          ))
          .all()
    )

⚠️ 串成兩個 `.filter()` 是 AND，那就變回交集了。一定要 `or_`。

算某個人的統計時只走 A（`user_id.in_(users)`），不要加 B——
B 會把帳本裡別人的錢算進這個人的總額。

要擋單一目標（例如 `GET /api/transactions?userId=U3`）：

    scope.require_user(target_id, scope.queryable_users(
        me_id, guardianships, group_members))
    scope.require_group(group_id, groups)

`queryable_users` 比 `visible_users` 寬：跟我同帳本的人，我看得到他在
那本帳裡的紀錄，所以「查他」是合理的——只是查到的會是那一部分。

⚠️ **沒權限要回 403，不要回空陣列。**
回空的話，前端分不出「這個人沒記帳」和「你不能看」。
"""

from __future__ import annotations

from typing import Iterable, Protocol, Sequence

__all__ = [
    "Forbidden",
    "visible_users",
    "co_members",
    "queryable_users",
    "can_see_row",
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


def co_members(me: object, group_members: Iterable[object]) -> set:
    """跟我同帳本的人（含我自己）。

    這些人我看得到他們**在共用帳本裡**的紀錄——但看不到他們記在別處的。
    這跟監管不一樣：監管是整個人，共用帳本只是那一本。

    >>> gm = [{"group_id": "G1", "user_id": "U1"},
    ...       {"group_id": "G1", "user_id": "U2"},
    ...       {"group_id": "G9", "user_id": "U7"}]
    >>> co_members("U1", gm) == {"U1", "U2"}
    True
    """
    mine = visible_groups(me, group_members)
    out = {me}
    for m in group_members:
        if _attr(m, "group_id", "group") in mine:
            out.add(_attr(m, "user_id", "user"))
    return out


def queryable_users(
    me: object,
    guardianships: Iterable[object],
    group_members: Iterable[object],
) -> set:
    """我可以拿誰的 id 來查：我監管的人 ＋ 跟我同帳本的人。

    ⚠️ 「查得到」不等於「看得到全部」。同帳本的人只會查到共用帳本那部分，
    這由 :func:`can_see_row` 逐筆決定——這裡只負責擋掉完全無關的人。
    """
    return visible_users(me, guardianships) | co_members(me, group_members)


def can_see_row(
    row: object, users: Iterable[object], groups: Iterable[object]
) -> bool:
    """這一筆我看不看得到：A 或 B，過一條就算。

    >>> can_see_row({"user_id": "U3", "group_id": "G9"}, {"U1", "U3"}, {"G1"})
    True
    >>> can_see_row({"user_id": "U9", "group_id": "G1"}, {"U1"}, {"G1"})
    True
    >>> can_see_row({"user_id": "U9", "group_id": "G9"}, {"U1"}, {"G1"})
    False
    """
    return (
        _attr(row, "user_id", "user") in set(users)
        or _attr(row, "group_id", "group") in set(groups)
    )


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
    """留下看得到的：A 或 B，過一條就留。

    這是給「已經在記憶體裡的資料」用的（例如測試、或算統計時的中間結果）。
    ⚠️ 正式查詢請把條件下到 SQL 的 WHERE，不要整張表撈出來再篩——
    資料一多就是全表掃描。

    >>> rows = [{"user_id": "U3", "group_id": "G1"},
    ...         {"user_id": "U3", "group_id": "G3"},
    ...         {"user_id": "U2", "group_id": "G1"},
    ...         {"user_id": "U9", "group_id": "G9"}]
    >>> filter_rows(rows, {"U1", "U3"}, {"G1"})  # doctest: +NORMALIZE_WHITESPACE
    [{'user_id': 'U3', 'group_id': 'G1'},
     {'user_id': 'U3', 'group_id': 'G3'},
     {'user_id': 'U2', 'group_id': 'G1'}]
    """
    us, gs = set(users), set(groups)
    return [r for r in rows if can_see_row(r, us, gs)]
