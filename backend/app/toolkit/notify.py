"""
通知要發給誰：把所有理由合起來，然後去重。

負責人：成員4（家庭與可見範圍）

===========================================================================
一句話
===========================================================================
**一筆紀錄對一個人最多產生一則通知。**

一個人可能同時有好幾個理由收到同一筆：

    · 他監管記帳的那個人          → 跨所有帳本，無條件
    · 他在這本帳裡，而且開了訂閱   → 只限這一本

父母最容易同時滿足兩個：既是子女的監管者，又跟子女在同一本旅遊帳裡。
不去重的話，他會收到兩則一模一樣的通知——同一個時間、同一筆金額、
同一個人。使用者不會覺得「系統很周到」，只會覺得壞掉了。

===========================================================================
誰優先
===========================================================================
**監管優先。**

監管是跨帳本的，涵蓋這個人記的每一筆；帳本訂閱只涵蓋那一本。
所以監管是比較強的理由，通知上也該這樣標——標成「帳本」的話，
父母會以為「我只看得到這本帳」，那是錯的。

換個角度看：帳本訂閱真正補上的，是**我沒有監管的人**記的紀錄
（一起出遊的朋友、配偶）。監管對象的部分早就被涵蓋了。

===========================================================================
還要在資料庫擋一次
===========================================================================
`notifications` 有 `UNIQUE (recipient_id, transaction_id)`。

理由是：去重寫在應用層，重試、並行、補跑都可能繞過它。
唯一索引是最後一道，而且它不會忘記。

===========================================================================
怎麼用
===========================================================================
    from app.toolkit import notify

    for user_id, reason in notify.recipients_for(tx, guardianships, members):
        create_notification(user_id, tx, reason)   # reason: 'guardian' / 'ledger'
"""

from __future__ import annotations

from typing import Iterable

from .scope import _attr

__all__ = ["GUARDIAN", "LEDGER", "recipients_for"]

#: 因為我監管記帳的那個人
GUARDIAN = "guardian"
#: 因為我在這本帳裡，而且開了訂閱
LEDGER = "ledger"


def _subscribed(member: object) -> bool:
    """這個成員有沒有訂閱這本帳。

    ⚠️ **沒有 notify 這個欄位就當成「沒訂閱」，不要丟例外。**
    欄位是後來才加的，舊資料、或還沒跑完 migration 的環境都可能沒有它。
    在這裡炸掉的話，整條通知流程會停——包括監管那一半，
    而那一半是這個系統的核心功能。預設安靜，比預設爆炸好。
    """
    if isinstance(member, dict):
        return bool(member.get("notify"))
    return bool(getattr(member, "notify", False))


def recipients_for(
    tx: object,
    guardianships: Iterable[object],
    group_members: Iterable[object],
) -> list[tuple]:
    """這一筆該通知誰，以及為什麼。已經去重。

    Args:
        tx: 一筆紀錄，要有 user_id / user 和 group_id / group。
        guardianships: 還有效的監管關係（`ended_at IS NULL` 請在 SQL 濾掉）。
        group_members: 這本帳的成員。只有 `notify` 為真的才算訂閱。

    Returns:
        `[(user_id, reason), ...]`，監管的排在前面，**記帳的人自己不在裡面**
        （沒有人需要被通知自己剛剛做了什麼）。

    >>> tx = {"user_id": "U3", "group_id": "G1"}
    >>> g = [{"guardian_id": "U1", "ward_id": "U3"}]
    >>> m = [{"group_id": "G1", "user_id": "U1", "notify": True},
    ...      {"group_id": "G1", "user_id": "U2", "notify": True},
    ...      {"group_id": "G1", "user_id": "U3", "notify": True}]
    >>> recipients_for(tx, g, m)
    [('U1', 'guardian'), ('U2', 'ledger')]
    """
    author = _attr(tx, "user_id", "user")
    group = _attr(tx, "group_id", "group")

    out: list[tuple] = []
    seen = {author}                       # 自己不通知自己

    # 監管先跑，它優先
    for g in guardianships:
        if _attr(g, "ward_id", "ward") != author:
            continue
        who = _attr(g, "guardian_id", "guardian")
        if who in seen:
            continue
        seen.add(who)
        out.append((who, GUARDIAN))

    # 再補上這本帳裡有訂閱、而且還沒被涵蓋的人
    for m in group_members:
        if _attr(m, "group_id", "group") != group:
            continue
        if not _subscribed(m):
            continue
        who = _attr(m, "user_id", "user")
        if who in seen:
            continue
        seen.add(who)
        out.append((who, LEDGER))

    return out
