"""
通知。

負責人：成員4（家庭）　✦ 分支：m4-access

三支 API 都已實作完成（已拿掉 @stub）：
* GET   /api/notifications         通知清單（輪詢）＋預算提醒檢查
* PATCH /api/notifications/{nid}   一則標記已讀
* PATCH /api/notifications         整批標記已讀（一定要帶 readUntil）

前端送什麼、要回什麼：docs/02-前後端串接契約.md 同名的章節
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.guards import block_admin, own
from app.models import AlertRule, Group, Notification, SavingsGoal, Transaction, User
from app.routers._stub import not_ready, stub
from app.schemas.family import ReadAllIn, ReadOneIn
from app.toolkit import alerts, crud, errors, money, period
from app.toolkit.db import get_db

router = APIRouter(tags=["通知"])
OWNER = "成員4"


@router.get("/notifications", summary="通知清單（輪詢）")
@block_admin
def list_notifications(
    me: User,
    since: str | None = None,
    unreadOnly: bool = False,
    db: Session = Depends(get_db),
):
    """通知清單（輪詢）

    GET /api/notifications

    右上角鈴鐺每 20 秒來拿一次。回傳：比 since 新的通知（由新到舊，最多 20 則）、
    全部未讀數 unread、我所有通知中最大的 id（maxId）。
    同時在這裡檢查「預算提醒」門檻：跨過門檻就寫一則 budget_alert，
    並用 alert_rules.fired_period 確保同一門檻一個月只響一次。

    重點：
    · since 是嚴格大於（>）
    · unread 是全部的未讀數，不是這一批的
    · maxId 另外查，不用這一批的最後一個
    · 查詢一律 WHERE recipient_id = 我
    """
    # 1. 我的提醒門檻：這個月跨過、還沒響過的，寫一則 budget_alert
    this_month = period.current_month(datetime.now(timezone(timedelta(hours=8))).date())
    rules = crud.find(AlertRule, {
        "user_id": me.id,
        "enabled": True,
        "or": [{"fired_period__isnull": True}, {"fired_period__ne": this_month}],
    }, db=db)
    if rules:
        start, end = period.month_range(this_month)
        mine = crud.find(Transaction, {"user_id": me.id, "kind__in": ["income", "expense"],
                                       "occurred_on__between": (start, end)},
                         fields=("group_id", "kind", "amount"), db=db)
        goals = {}
        for g in crud.find(SavingsGoal, {"user_id": me.id}, order_by="id", db=db):
            goals[g.group_id] = g.goal_amount                    # 整體目標的鍵是 None
        group_ids = list({r.group_id for r in rules if r.group_id})
        names = {g.id: g.name for g in crud.find(Group, {"id__in": group_ids}, db=db)} if group_ids else {}
        for rule in rules:
            rows = [t for t in mine if rule.group_id is None or t["group_id"] == rule.group_id]
            income = money.add(*[t["amount"] for t in rows if t["kind"] == "income"])
            spent = money.add(*[t["amount"] for t in rows if t["kind"] == "expense"])
            allowance = income - goals.get(rule.group_id, money.ZERO)
            reached = alerts.usage_percent(spent, allowance)
            if not alerts.should_fire(rule.percent, 0, reached, rule.fired_period, this_month):
                continue
            crud.save(Notification, {"recipient_id": me.id, "type": "budget_alert", "payload_json": {
                "percent": rule.percent,
                "reached": reached,
                "groupId": str(rule.group_id) if rule.group_id else None,
                "groupName": names.get(rule.group_id, "") if rule.group_id else "整體",
                "spent": float(spent),
                "allowance": float(allowance),
            }}, db=db)
            crud.save(AlertRule, {"id": rule.id, "fired_period": this_month}, db=db)
        db.commit()

    # 2. 我的通知：比 since 新的，由新到舊，一次最多 20 則
    where = {"recipient_id": me.id}
    if since:
        where["id__gt"] = int(since) if since.isdigit() else 0
    if unreadOnly:
        where["read_at__isnull"] = True
    rows = crud.find(Notification, where, order_by="-id", limit=20, db=db)

    # 3. 未讀總數、最大的 id 另外查（不受 since 影響）
    unread = crud.count(Notification, {"recipient_id": me.id, "read_at__isnull": True}, db=db)
    newest = crud.get(Notification, where={"recipient_id": me.id}, fields="id", order_by="-id", db=db)

    # 4. 記帳類補上那一筆的金額、分類、店家；提醒類把 payload 攤開
    tx_ids = [n.transaction_id for n in rows if n.transaction_id]
    txs = {t.id: t for t in crud.find(Transaction, {"id__in": tx_ids}, db=db)} if tx_ids else {}
    out = []
    for n in rows:
        stamps = []
        for value in (n.created_at, n.read_at):
            if value is not None and value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)          # SQLite 讀回來沒有時區
            stamps.append(value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if value else None)
        item = {
            "id": str(n.id),
            "type": n.type,
            "actorId": str(n.actor_id) if n.actor_id else None,
            "createdAt": stamps[0],
            "readAt": stamps[1],
        }
        item.update(n.payload_json or {})
        t = txs.get(n.transaction_id)
        if t is not None:
            item.update({"txId": str(t.id), "amount": t.amount, "cat": str(t.category_id),
                         "merchant": t.merchant or "", "groupId": str(t.group_id)})
        out.append(item)

    # 5. 回傳
    return {"notifications": out, "unread": unread, "maxId": str(newest) if newest else None}


@router.patch("/notifications/{nid}", summary="一則標記已讀")
def read_notification(
    body: ReadOneIn,
    row=Depends(own(Notification, "nid", "recipient_id")),
    db: Session = Depends(get_db),
):
    """一則標記已讀

    PATCH /api/notifications/{nid}

    把一則通知標成已讀（read=false 則改回未讀）。只能改自己的通知，
    權限（401／403／404）已由 own(...) 守衛處理。
    已讀過的再標一次，保留原本的時間。
    回傳 {"id", "readAt"}（UTC、結尾 Z）。
    """
    # 1. 標已讀（讀過的保留原本的時間）；read: false 是改回未讀
    read_at = (row.read_at or datetime.now(timezone.utc)) if body.read else None
    crud.save(Notification, {"id": row.id, "read_at": read_at}, db=db)
    db.commit()

    # 2. 回傳（UTC、結尾 Z）
    if read_at is not None and read_at.tzinfo is None:
        read_at = read_at.replace(tzinfo=timezone.utc)              # SQLite 讀回來沒有時區
    stamp = read_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if read_at else None
    return {"id": str(row.id), "readAt": stamp}


@router.patch("/notifications", summary="整批標記已讀")
@block_admin
def read_notifications(body: ReadAllIn, me: User, db: Session = Depends(get_db)):
    """整批標記已讀

    PATCH /api/notifications

    「全部已讀」：只把我的未讀通知標到 readUntil 為止。
    一定要帶 readUntil，避免按下去瞬間才進來、使用者沒看到的通知被一起標掉。
    沒帶 → 400。回傳 {"updated", "unread"}。
    """
    # 1. 一定要帶 readUntil：只標到使用者按下去當時看得到的那一則
    if not body.readUntil:
        raise errors.bad_request("要帶 readUntil（按下去當時最新的那一則）")
    until = int(body.readUntil) if body.readUntil.isdigit() else 0

    # 2. 我的、還沒讀、不比 readUntil 新的，一次標掉
    updated = crud.save(Notification, {"read_at": datetime.now(timezone.utc)},
                        where={"recipient_id": me.id, "read_at__isnull": True, "id__lte": until}, db=db)
    db.commit()

    # 3. 剩下的未讀（之後才進來的還是未讀）
    unread = crud.count(Notification, {"recipient_id": me.id, "read_at__isnull": True}, db=db)
    return {"updated": updated, "unread": unread}