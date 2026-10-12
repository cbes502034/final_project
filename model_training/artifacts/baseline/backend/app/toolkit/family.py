"""
家庭綁定：建立家庭、邀請碼、用帳號邀請。

負責人：成員4（家庭與可見範圍）

===========================================================================
兩種邀請
===========================================================================
    邀請碼    家長產生一組碼（例如 K7QM-3XWP），傳給家人，對方輸入就加入
    用帳號    家長輸入對方的 email，找到人之後送出邀請，對方在自己的畫面上按「加入」

兩種都由**家長**發起，而且**身分（家長／子女）由發邀請的家長決定**，
被邀請的人不能自己選——否則任何拿到碼的人都能以家長身分加入。

===========================================================================
幾條不能鬆的規則
===========================================================================
* 邀請碼**只能用一次**，七天後過期。資料庫只存雜湊，不存明碼。
* 用帳號找人只接受**完整的 email**，不做模糊搜尋——模糊搜尋等於送出一份
  「這個系統裡有哪些人」的名單。找到的人只回名字與頭像，**不回任何財務資料**。
* 一個人同時只屬於一個家庭。已經在家庭裡的人不能再被邀請，
  回應時也不說他在哪個家庭（`unavailable`），只說「目前不能邀請」。
* 平台管理員不屬於任何家庭，不能被邀請。

===========================================================================
怎麼用
===========================================================================
    from app.toolkit import family

    code = family.new_code()                  # 'K7QM-3XWP'，給使用者看
    row.code_hash = family.hash_code(code)    # 只存這個

    family.require_can_invite(me_role)        # 不是家長就丟 Forbidden
    family.require_joinable(invite, now)      # 用過、過期、被取消就丟 ValueError

    family.require_can_dissolve(my_role, other_parents)            # DELETE /api/family
    family.require_can_change_role(me, my_role, target, target_role, new_role, parent_count)
    family.require_can_guard(me, my_role, ward_role, same_family)   # POST /api/guardianships
    family.require_can_end_guard(me, my_role, guardian, same_family) # DELETE /api/guardianships/{id}

===========================================================================
離開家庭的三條路（都不刪任何一筆紀錄）
===========================================================================
    移出    家長把子女移出                         require_can_remove
    退出    自己離開；唯一的家長在家裡還有人時不行   require_can_leave
    解散    唯一的家長一次讓所有人離開             require_can_dissolve
            ⚠️ 還有別的家長時不能解散——一個人不能替另一位家長決定。
               那時你本來就可以自己退出（家裡還有家長，退出不會卡住）。
    三條路都要在同一個交易裡收掉：監管關係（設 ended_at，零用金一起結束）、
    家人之間的帳本成員、還沒用的邀請與邀請碼。
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from .scope import Forbidden

__all__ = [
    "INVITE_TTL_DAYS",
    "ROLES",
    "CODE_ALPHABET",
    "new_code",
    "normalize_code",
    "hash_code",
    "expires_at",
    "clean_family_name",
    "clean_role",
    "require_can_invite",
    "lookup_status",
    "require_joinable",
    "require_can_remove",
    "require_can_dissolve",
    "require_can_change_role",
    "require_can_guard",
    "require_can_end_guard",
    "require_can_leave",
    "require_has_parent",
]

#: 邀請多久之後失效。
INVITE_TTL_DAYS = 7

#: 邀請時可以指定的身分。
ROLES = ("parent", "child")

#: 邀請碼用的字元：拿掉 0/O、1/I/L 這些手寫或唸出來會搞混的。
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def new_code() -> str:
    """產生一組 8 碼的邀請碼，中間用 - 分開方便念：`K7QM-3XWP`。

    ⚠️ 用 `secrets`，不要用 `random`——`random` 的結果猜得出來。
    """
    raw = "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))
    return raw[:4] + "-" + raw[4:]


def normalize_code(raw: object) -> str:
    """使用者打的碼：去掉空白與 -，轉大寫。`k7qm 3xwp` → `K7QM3XWP`。"""
    return "".join(ch for ch in str(raw or "").upper() if ch.isalnum())


def hash_code(code: object) -> str:
    """邀請碼的雜湊。資料庫只存這個，比對時也先正規化再算。"""
    return hashlib.sha256(normalize_code(code).encode("utf-8")).hexdigest()


def expires_at(now: datetime | None = None, days: int | None = None) -> datetime:
    """從現在起算幾天（預設 INVITE_TTL_DAYS；路由傳 settings.invite_ttl_days）。"""
    now = now or datetime.now(timezone.utc)
    return now + timedelta(days=INVITE_TTL_DAYS if days is None else days)


def clean_family_name(name: object) -> str:
    """家庭名稱：去頭尾空白、最多 20 字；空的丟 ValueError。"""
    text = " ".join(str(name or "").split())
    if not text:
        raise ValueError("幫你的家庭取個名字，例如「林家」")
    return text[:20]


def clean_role(role: object) -> str:
    """邀請時指定的身分，只認 parent / child。"""
    if role not in ROLES:
        raise ValueError("身分只能是家長或子女")
    return str(role)


def require_can_invite(my_role: object) -> None:
    """只有家長能邀請人、產生邀請碼。"""
    if my_role != "parent":
        raise Forbidden("只有家長可以邀請家人")


def lookup_status(
    target_is_admin: bool,
    target_family_id: object,
    my_family_id: object,
    has_pending_invite: bool,
) -> str:
    """用帳號找到人之後，他現在能不能被邀請。

    回傳：
        available   可以邀請
        member      已經在你的家庭裡
        invited     已經邀請過，對方還沒回覆
        unavailable 目前不能邀請（在別的家庭，或是平台管理員）
                    ⚠️ 刻意不說原因——不要透露他在哪個家庭。

    >>> lookup_status(False, None, "F1", False)
    'available'
    >>> lookup_status(False, "F2", "F1", False)
    'unavailable'
    >>> lookup_status(True, None, "F1", False)
    'unavailable'
    """
    if target_is_admin:
        return "unavailable"
    if target_family_id is not None and target_family_id == my_family_id:
        return "member"
    if target_family_id is not None:
        return "unavailable"
    if has_pending_invite:
        return "invited"
    return "available"


def require_joinable(status: object, expires: datetime, now: datetime | None = None) -> None:
    """邀請（或邀請碼）還能不能用。不能就丟 ValueError，路由層轉成 400。

    >>> from datetime import datetime, timezone, timedelta
    >>> t = datetime(2026, 9, 14, tzinfo=timezone.utc)
    >>> require_joinable("pending", t + timedelta(days=1), t)
    >>> require_joinable("used", t + timedelta(days=1), t)
    Traceback (most recent call last):
    ...
    ValueError: 這個邀請已經用過了
    """
    now = now or datetime.now(timezone.utc)
    if status == "used" or status == "accepted":
        raise ValueError("這個邀請已經用過了")
    if status in ("declined", "cancelled"):
        raise ValueError("這個邀請已經取消了")
    if status != "pending":
        raise ValueError("這個邀請不能用")
    if now >= expires:
        raise ValueError("這個邀請已經過期了，請家人重新邀請一次")


def require_can_remove(me: object, my_role: object, target: object, target_role: object) -> None:
    """家長把某個人移出家庭之前的檢查。不行就丟 Forbidden／ValueError。

    ⚠️ **家長不能移除另一位家長。** 另一位家長只能自己退出——
    不然兩個人意見不合時，一方就能把另一方踢出家門。

    >>> require_can_remove("U1", "parent", "U3", "child")
    """
    if my_role != "parent":
        raise Forbidden("只有家長可以移除成員")
    if me == target:
        raise ValueError("要離開請用「退出家庭」")
    if target_role != "child":
        raise Forbidden("另一位家長只能自己退出，不能被移除")


def require_can_leave(my_role: object, other_parents: int, other_members: int) -> None:
    """自己退出家庭之前的檢查。

    任何人都可以退出——這是自由意願。唯一的例外：
    **唯一的家長**不能在家裡還有其他人的時候退出，孩子會留在一個沒人能管理的家。

    >>> require_can_leave("child", 0, 3)
    >>> require_can_leave("parent", 0, 0)          # 家裡只剩自己，可以
    >>> require_can_leave("parent", 0, 2)
    Traceback (most recent call last):
    ...
    ValueError: 你是這個家唯一的家長。先邀請另一位家長，或把其他成員移出，才能退出
    """
    if my_role == "parent" and other_parents == 0 and other_members > 0:
        raise ValueError("你是這個家唯一的家長。先邀請另一位家長，或把其他成員移出，才能退出")


def require_can_dissolve(my_role: object, other_parents: int) -> None:
    """解散家庭之前的檢查：只有家長，而且是**唯一的家長**。

    >>> require_can_dissolve("parent", 0)
    >>> require_can_dissolve("parent", 1)
    Traceback (most recent call last):
    ...
    ValueError: 家裡還有其他家長，不能一個人解散。你可以自己退出家庭
    """
    if my_role != "parent":
        raise Forbidden("只有家長可以解散家庭")
    if other_parents > 0:
        raise ValueError("家裡還有其他家長，不能一個人解散。你可以自己退出家庭")


def require_can_change_role(me: object, my_role: object, target: object, target_role: object,
                            new_role: object, parent_count: int) -> None:
    """改家庭角色之前的檢查（PATCH /api/family/members/{id}）。

    * 家長可以把子女設為家長
    * 家長可以把**自己**改成子女，但家裡要還有別的家長
    * ⚠️ 不能把另一位家長改成子女——那跟「移除另一位家長」是同一件事

    設為家長時，他被照看的關係要一起結束（家長之間本來就看得到）；
    自己改成子女時，他照看別人的關係要一起結束。

    >>> require_can_change_role("U1", "parent", "U3", "child", "parent", 1)
    >>> require_can_change_role("U1", "parent", "U1", "parent", "child", 1)
    Traceback (most recent call last):
    ...
    ValueError: 你是唯一的家長，先把另一位家人設為家長
    """
    if my_role != "parent":
        raise Forbidden("只有家長可以改角色")
    clean_role(new_role)
    if new_role == target_role:
        return
    if new_role == "child":
        if me != target:
            raise Forbidden("不能把另一位家長改成子女，他只能自己調整")
        if parent_count < 2:
            raise ValueError("你是唯一的家長，先把另一位家人設為家長")


def require_can_guard(me: object, my_role: object, ward_role: object, same_family: bool,
                      already: bool = False) -> None:
    """開始照看一個人之前的檢查（POST /api/guardianships）。監管人一定是自己。

    >>> require_can_guard("U1", "parent", "child", True)
    >>> require_can_guard("U1", "parent", "parent", True)
    Traceback (most recent call last):
    ...
    ValueError: 只能照看子女；家長之間本來就看得到彼此
    """
    if my_role != "parent":
        raise Forbidden("只有家長可以照看家人")
    if not same_family:
        raise LookupError("這個家庭裡沒有這個人")
    if ward_role != "child":
        raise ValueError("只能照看子女；家長之間本來就看得到彼此")
    if already:
        raise ValueError("已經在照看這個人了")


def require_can_end_guard(me: object, my_role: object, guardian: object, same_family: bool) -> None:
    """解除監管之前的檢查（DELETE /api/guardianships/{id}）：監管人自己，或同一個家庭的家長。

    ⚠️ 被照看的人不能自己解除——他可以退出家庭，但監管的意義就是「不是他說停就停」。
    也正因為這樣，監管一定要雙向可見。

    >>> require_can_end_guard("U1", "parent", "U1", True)
    >>> require_can_end_guard("U2", "parent", "U1", True)     # 同一家的另一位家長也可以
    """
    if me == guardian:
        return
    if my_role != "parent" or not same_family:
        raise Forbidden("只有家長可以解除監管")


def require_has_parent(parent_count: int) -> None:
    """用邀請碼加入、或接受邀請之前的檢查：家裡至少要有一位家長。

    ⚠️ 家長離開時要一起作廢他產生、還沒用過的邀請碼。兩道一起擋，
    才不會出現「只有子女、沒有家長」的家——那種家沒有人能邀請或管理。

    >>> require_has_parent(1)
    >>> require_has_parent(0)
    Traceback (most recent call last):
    ...
    ValueError: 這個家目前沒有家長，暫時不能加入
    """
    if parent_count < 1:
        raise ValueError("這個家目前沒有家長，暫時不能加入")
