"""活動的「目標金額」：一個提醒，到了就通知一次。

目標金額是使用者自己定義的：想存錢就訂高一點當儲蓄目標，想控制花費就訂低一點當警訊。
系統不分類型，只看這個活動「自建立以來」的帳：
    活動裡還沒有任何收入 → 比的是累計支出（花到這個數字了）
    有收入                → 比的是累計結餘（存到這個數字了）
到達的那一刻通知那位成員一次；改了目標金額，到了會再通知一次。

目標金額存在 savings_goals（user_id ＋ group_id，最新一列為準），每位成員各訂各的。
guards.current_user 每次請求呼叫 check；沒有訂活動目標的人只多一個查詢。
"""
from __future__ import annotations

from app.models import Group, GroupMember, Notification, SavingsGoal, Transaction
from app.toolkit import crud, money


def progress(db, group_id: int) -> dict:
    """活動自建立以來的累計：{"income", "expense", "metric", "value"}。前端的活動總覽也照這個規則畫。"""
    income = expense = money.ZERO
    for t in crud.find(Transaction, {"group_id": group_id, "kind__in": ["income", "expense"]},
                       fields=("kind", "amount"), db=db):
        if t["kind"] == "income":
            income += t["amount"]
        else:
            expense += t["amount"]
    if income > 0:
        return {"income": income, "expense": expense, "metric": "saved", "value": income - expense}
    return {"income": income, "expense": expense, "metric": "spent", "value": expense}


def check(db, user) -> None:
    goals = {}
    for row in crud.find(SavingsGoal, {"user_id": user.id, "group_id__isnull": False}, order_by="id", db=db):
        goals[row.group_id] = row.goal_amount                  # 後面的蓋掉前面的，留下最新的
    goals = {g: a for g, a in goals.items() if a and a > 0}
    if not goals:
        return
    mine = set(crud.find(GroupMember, {"user_id": user.id, "group_id__in": list(goals)}, fields="group_id", db=db))
    groups = {g.id: g for g in crud.find(Group, {"id__in": list(mine), "personal_owner_id__isnull": True,
                                                  "removed_at__isnull": True}, db=db)}
    if not groups:
        return
    fired = {(str(n.payload_json.get("groupId")), float(n.payload_json.get("goal", 0)))
             for n in crud.find(Notification, {"recipient_id": user.id, "type": "activity_target"}, db=db)
             if n.payload_json}
    wrote = False
    for gid, group in groups.items():
        goal = money.quantize(goals[gid])
        if (str(gid), float(goal)) in fired:
            continue
        p = progress(db, gid)
        if p["value"] < goal:
            continue
        crud.save(Notification, {"recipient_id": user.id, "type": "activity_target", "payload_json": {
            "groupId": str(gid), "groupName": group.name, "goal": float(goal),
            "value": float(p["value"]), "metric": p["metric"]}}, db=db)
        wrote = True
    if wrote:
        db.commit()
