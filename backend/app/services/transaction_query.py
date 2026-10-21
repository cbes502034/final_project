"""收支明細與年月包裹共用相同的權限、來源與搜尋條件。"""
from datetime import date

from app.guards import visible_scope
from app.models import Group, GroupMember, Transaction, User
from app.toolkit import crud, errors


def filters(db, me, userId=None, groupId=None, from_=None, to=None, categoryId=None,
            kind=None, source=None, q=None, activityId=None):
    users, groups = visible_scope(me, db)
    where = {"and": [{"or": [{"user_id__in": users}, {"group_id__in": groups}]}]}
    if userId and userId != "all":
        target = int(userId) if userId.isdigit() else 0
        members = crud.find(GroupMember, {"group_id__in": groups}, fields="user_id", db=db)
        if target not in users and target not in members and not crud.exists(
                Transaction, {"user_id": target, "group_id__in": groups}, db=db):
            raise errors.forbidden("你沒有權限看這個人的紀錄")
        where["user_id"] = target
    if groupId and groupId != "all":
        gid = int(groupId) if groupId.isdigit() else 0
        if gid not in groups:
            raise errors.forbidden("你不在這個活動裡")
        where["group_id"] = gid
    else:
        where["is_snapshot"] = False
    try:
        if from_:
            where["occurred_on__gte"] = date.fromisoformat(from_)
        if to:
            where["occurred_on__lte"] = date.fromisoformat(to)
    except ValueError:
        raise errors.unprocessable("日期要是 YYYY-MM-DD") from None
    if categoryId:
        where["category_id"] = int(categoryId) if categoryId.isdigit() else 0
    for name, value, valid in (("kind", kind, ("income", "expense", "transfer")),
                                ("source", source, ("manual", "nlp", "import"))):
        if value and value != "all":
            if value not in valid:
                raise errors.unprocessable(name + " 只能是 " + "、".join(valid))
            where[name] = value
    if activityId and activityId != "all":
        if activityId == "none":
            personal = crud.find(Group, {"personal_owner_id__isnull": False}, fields="id", db=db)
            where["origin_group_id__isnull"] = True
            where["group_id__in"] = personal
        else:
            gid = int(activityId) if activityId.isdigit() else 0
            where["and"].append({"or": [{"origin_group_id": gid}, {"group_id": gid}]})
    if q and q.strip():
        word = q.strip()
        activities = crud.find(Group, {"name__icontains": word, "personal_owner_id__isnull": True}, fields="id", db=db)
        where["and"].append({"or": [{"merchant__icontains": word}, {"note__icontains": word},
                                    {"origin_group_id__in": activities}, {"group_id__in": activities}]})
    return where


def annotate(db, rows, items):
    ids = {t.origin_group_id or t.group_id for t in rows}
    activities = {g.id: g for g in crud.find(Group, {"id__in": ids, "personal_owner_id__isnull": True}, db=db)}
    authors = {u.id: u.display_name for u in crud.find(User, {"id__in": {t.user_id for t in rows}}, db=db)}
    for row, item in zip(rows, items):
        origin = activities.get(row.origin_group_id or row.group_id)
        item["activityId"] = str(origin.id) if origin else None
        item["activityName"] = origin.name if origin else "自行記錄"
        item["userName"] = authors.get(row.user_id, "")
