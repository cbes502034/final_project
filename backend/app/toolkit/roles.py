"""
角色：誰能做哪些「治理動作」。

負責人：成員4（家庭與可見範圍）

===========================================================================
一句話
===========================================================================
角色決定「**能做什麼**」，監管關係決定「**看得到誰**」。兩者不交叉。

這句話是這個模組存在的全部理由。要判斷看不看得到某個人的紀錄，
請用 `app.toolkit.scope`，不要用這裡的任何東西。

===========================================================================
三個層級
===========================================================================
    平台   master   系統管理員。不屬於任何家庭。
    家庭   parent   家長：邀請成員、設家庭預算、建立監管關係
    家庭   child    子女：記自己的帳

`master` **不是**家庭角色。它不會出現在 `family_members.role` 裡，
一個家庭沒有「最高權限的那個人」——家長就是家長。

===========================================================================
為什麼不用年齡分
===========================================================================
系統只提供功能，怎麼用是那一家自己的事。

有些家庭覺得十六歲就該自己管錢，有些覺得二十五歲還要看著。
兩種都不關系統的事——我們提供監管關係這個工具，要不要建立、
建立在誰身上，由那個家庭決定。

所以 `users.birth_year` 純粹是個人資料，**任何權限判斷都不准讀它**。
一旦寫了 `if age < 18`，系統就開始替別人的家庭做價值判斷了。

===========================================================================
平台管理員為什麼看不到任何帳
===========================================================================
`master` 能停權，但讀不到任何一筆紀錄。

這跟「管理人員不可以進入子女的帳號」是同一條原則：
**停權是關門，不是配鑰匙。**

一個能讀全系統消費明細的帳號，比家長越權嚴重得多——家長至少還在
`guardianships` 表上留下痕跡、被監管的人看得到；平台管理員如果能看，
那是一個沒有人看得見的視角。所以這裡直接不提供那個能力。

===========================================================================
怎麼用
===========================================================================
    from app.toolkit import roles

    roles.require_govern(me.role, "invite_member")     # 不是家長就丟 Forbidden

    if roles.can_set_goal_for(me.id, target_id, guardianships):
        ...

    roles.require_platform("suspend_user", me.is_platform_admin)
"""

from __future__ import annotations

from typing import Iterable

from .scope import Forbidden, visible_users

__all__ = [
    "FAMILY_ROLES",
    "PARENT",
    "CHILD",
    "GOVERN_ACTIONS",
    "PLATFORM_ACTIONS",
    "is_family_role",
    "can_govern",
    "require_govern",
    "can_set_goal_for",
    "require_set_goal",
    "can_platform",
    "require_platform",
]

PARENT = "parent"
CHILD = "child"

#: 家庭裡只有這兩種角色。master 不在裡面——它是平台層級的。
FAMILY_ROLES: tuple[str, ...] = (PARENT, CHILD)

#: 治理動作 → 哪些家庭角色可以做。
#:
#: ⚠️ 這張表裡**沒有任何一項是「看誰的資料」**。要加那種東西之前先想清楚：
#: 可見範圍只能來自 guardianships，不然「誰看得到我」就列不出來了。
GOVERN_ACTIONS: dict[str, frozenset[str]] = {
    "invite_member": frozenset({PARENT}),
    "remove_member": frozenset({PARENT}),
    "change_member_role": frozenset({PARENT}),
    "set_family_budget": frozenset({PARENT}),
    "view_family_overview": frozenset({PARENT}),
    "create_guardianship": frozenset({PARENT}),
    "end_guardianship": frozenset({PARENT}),
    # 以下刻意兩種角色都可以——記帳的分類方式是個人的事，
    # 不該由家裡的階級決定。
    "create_group": frozenset({PARENT, CHILD}),
    "manage_own_group": frozenset({PARENT, CHILD}),
    "set_own_budget": frozenset({PARENT, CHILD}),
    "set_own_alerts": frozenset({PARENT, CHILD}),
    "export_own_data": frozenset({PARENT, CHILD}),
}

#: 平台管理員能做的事。**只有這三件，而且都不碰財務資料。**
PLATFORM_ACTIONS: frozenset[str] = frozenset(
    {"suspend_user", "unsuspend_user", "read_audit_log"}
)


def is_family_role(role: object) -> bool:
    """`role` 是不是合法的家庭角色。

    `'master'` 會回 False —— 它不是家庭角色，別讓它混進 family_members。
    """
    return role in FAMILY_ROLES


def can_govern(role: object, action: str) -> bool:
    """`role` 能不能做 `action` 這個治理動作。

    未知的 action 一律 False。寧可擋掉打錯字的呼叫，
    也不要因為查不到就放行——放行的那種寫法會讓漏掉的權限檢查
    看起來像正常運作。
    """
    allowed = GOVERN_ACTIONS.get(action)
    if allowed is None:
        return False
    return role in allowed


def require_govern(role: object, action: str) -> None:
    """不能做就丟 `Forbidden`。"""
    if not can_govern(role, action):
        raise Forbidden("這個動作需要家長權限：%s" % action)


def can_set_goal_for(
    me: object, target: object, guardianships: Iterable[object]
) -> bool:
    """我能不能設定 `target` 的每月存款目標。

    自己一定可以；別人要有監管關係。

    ⚠️ 不看角色、也不看年齡。家長不會因為是家長就能改任何人的目標——
    要改誰的，就得先有那條監管關係，而那條關係被監管的人自己看得到。
    """
    return target in visible_users(me, guardianships)


def require_set_goal(
    me: object, target: object, guardianships: Iterable[object]
) -> None:
    """不能設就丟 `Forbidden`。"""
    if not can_set_goal_for(me, target, guardianships):
        raise Forbidden("只能設定自己或你監管對象的存款目標")


def can_platform(action: str, is_platform_admin: object) -> bool:
    """平台管理員能不能做 `action`。

    `action` 不在 :data:`PLATFORM_ACTIONS` 裡就是 False——包含所有
    讀取財務資料的動作。**這是刻意的，不要往那張表裡加東西。**
    """
    if not is_platform_admin:
        return False
    return action in PLATFORM_ACTIONS


def require_platform(action: str, is_platform_admin: object) -> None:
    """不能做就丟 `Forbidden`。"""
    if not can_platform(action, is_platform_admin):
        raise Forbidden("這個動作需要平台管理員權限，且僅限停權與稽核：%s" % action)
