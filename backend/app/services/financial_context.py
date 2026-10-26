"""個人、家庭及活動的財務對象；彙總權限與個別明細權限分開處理。"""
from datetime import datetime, timedelta, timezone

from app.guards import visible_scope
from app.models import Family, FamilyMember, Group, GroupMember, Transaction
from app.toolkit import crud, errors, money


def resolve(db, me, scope=None, group_id=None):
    scope = scope or "me"
    if scope not in ("me", "family"):
        raise errors.unprocessable("scope 只能是 me 或 family")
    if scope == "family":
        if me.family_role != "parent" or not me.family_id:
            raise errors.forbidden("只有家庭中的家長可以切換家庭模式")
        members = crud.find(FamilyMember, {"family_id": me.family_id, "status": "active"}, db=db)
        people = {m.user_id for m in members}
        return {"people": people, "earners": {m.user_id for m in members if m.role == "parent"},
                "group": None, "personal_only": True, "scope": scope}
    selected = None
    if group_id and group_id != "all":
        gid = int(group_id) if str(group_id).isdigit() else 0
        _, groups = visible_scope(me, db)
        if gid not in groups:
            raise errors.forbidden("你不在這個活動裡")
        selected = crud.get(Group, gid, db=db)
    activity = selected and selected.personal_owner_id is None
    people = {me.id}
    if activity:
        people = set(crud.find(GroupMember, {"group_id": selected.id}, fields="user_id", db=db))
        people.update(crud.find(Transaction, {"group_id": selected.id}, fields="user_id", db=db))
    return {"people": people, "earners": people, "group": selected if activity else None,
            "personal_only": not activity, "scope": scope}


def personal_ids(db, people):
    return crud.find(Group, {"personal_owner_id__in": people}, fields="id", db=db)


def family_goal(db, fam):
    """自家庭建立日起的已入帳結餘；不混入未結束活動、預計收入或零用金收入。"""
    tw = timezone(timedelta(hours=8))
    created = fam.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    start, today = created.astimezone(tw).date(), datetime.now(tw).date()
    members = crud.find(FamilyMember, {"family_id": fam.id, "status": "active"}, db=db)
    people, earners = {m.user_id for m in members}, {m.user_id for m in members if m.role == "parent"}
    income, expense = money.ZERO, money.ZERO
    from app.services.allowance_ledger import internal_transfer_ids
    skip = internal_transfer_ids(db, people)                  # 家長給孩子的零用金是家裡換手，不算支出
    for t in crud.find(Transaction, {"group_id__in": personal_ids(db, people), "user_id__in": people,
                                    "is_snapshot": False, "occurred_on__between": (start, today)}, db=db):
        if t.id in skip:
            continue
        if t.kind == "income" and t.user_id in earners:
            income += t.amount
        elif t.kind == "expense":
            expense += t.amount
    net = income - expense
    goal = fam.goal_amount or money.ZERO
    return {"amount": goal, "note": fam.goal_note or "", "since": start.isoformat(),
            "income": income, "expense": expense, "accumulated": net,
            "remaining": max(money.ZERO, goal - net),
            "ratio": money.quantize(money.ratio(max(money.ZERO, net), goal), 4) if goal else money.ZERO}
