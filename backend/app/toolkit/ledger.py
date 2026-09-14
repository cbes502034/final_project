"""
帳本的生命週期：記帳、結算、封存、移除。

負責人：成員2（記帳）

===========================================================================
四個狀態
===========================================================================
    使用中    可以記帳、改設定、加減人
    已結算    活動帳本才有。唯讀：不能再記新的帳、不能改成員
    已封存    收起來不用。紀錄都在，隨時可以復原
    已移除    結算過的活動帳本才能移除。帳本不見、不能復原——**紀錄不刪**

===========================================================================
⚠️ 移除的是「帳本」，不是紀錄
===========================================================================
紀錄是記帳的人的。移除之後每一筆仍在他自己的收支明細與統計裡，
過去月份的數字不會變（groups.removed_at 有值，transactions 一筆都不動）。
會變的只有「靠這本帳才看得到別人紀錄」的那條路——帳本不在了，那條路就斷了。

為什麼不做成真的刪除：
  * 共用帳本裡有別人記的帳，建立者一刪就把家人的資料刪了
  * 九月的支出總額會憑空變少，跟「過去月份維持當時的數字」衝突

===========================================================================
怎麼用
===========================================================================
    from app.toolkit import ledger

    ledger.require_open(group.settled_at)          # 新增一筆之前；結算過就丟 ValueError → 409
    ledger.require_removable(me, group.created_by, group.settled_at, group.removed_at)
"""

from __future__ import annotations

from .scope import Forbidden

__all__ = ["require_open", "require_removable"]


def require_open(settled_at: object) -> None:
    """往這本帳記一筆之前的檢查：結算過的帳本唯讀。

    >>> require_open(None)
    >>> require_open("2026-09-14")
    Traceback (most recent call last):
    ...
    ValueError: 這本帳已經結算，不能再記新的帳
    """
    if settled_at:
        raise ValueError("這本帳已經結算，不能再記新的帳")


def require_removable(me: object, owner: object, settled_at: object, removed_at: object) -> None:
    """移除帳本之前的檢查。

    只有建立者；只有結算過的（還在用的帳本請用封存，封存可以復原）。

    >>> require_removable("U1", "U1", "2026-09-14", None)
    >>> require_removable("U1", "U1", None, None)
    Traceback (most recent call last):
    ...
    ValueError: 只有結算過的活動帳本可以移除；還在用的帳本請改用封存
    """
    if removed_at:
        raise ValueError("這本帳已經移除了")
    if me != owner:
        raise Forbidden("只有建立這本帳的人可以移除")
    if not settled_at:
        raise ValueError("只有結算過的活動帳本可以移除；還在用的帳本請改用封存")
