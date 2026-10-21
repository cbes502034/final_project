"""活動加入只建立 GroupMember，不改動家庭、角色或監管。"""
from datetime import datetime, timezone

from sqlalchemy import select

from app.models import ActivityInvite, Group, GroupMember, User
from app.toolkit import crud, errors, family


def create(db, group, me, email=None, label="朋友"):
    if group.personal_owner_id is not None or group.removed_at or group.settled_at or group.archived_at:
        raise errors.conflict("這個活動目前不能邀請朋友")
    if group.created_by != me.id:
        raise errors.forbidden("只有活動建立者可以邀請朋友")
    invitee = None
    code = None
    if email:
        invitee = crud.get(User, where={"email": email.strip().lower(), "deleted_at__isnull": True}, db=db)
        if not invitee or invitee.is_platform_admin:
            raise errors.not_found("找不到這個朋友的帳號")
        if crud.exists(GroupMember, {"group_id": group.id, "user_id": invitee.id}, db=db):
            raise errors.conflict("這位朋友已經在活動裡")
        if crud.exists(ActivityInvite, {"group_id": group.id, "invitee_id": invitee.id,
                                       "status": "pending", "expires_at__gt": datetime.now(timezone.utc)}, db=db):
            raise errors.conflict("邀請已送出，等待朋友回覆")
    else:
        code = family.new_code()
    row = crud.save(ActivityInvite, {
        "group_id": group.id, "inviter_id": me.id, "invitee_id": invitee.id if invitee else None,
        "code_hash": family.hash_code(code) if code else None, "label": label,
        "expires_at": family.expires_at(),
    }, db=db)
    return {"id": str(row.id), "groupId": str(group.id), "code": code,
            "expiresAt": row.expires_at.isoformat(), "status": row.status}


def respond(db, me, invite_id=None, action="accept", code=None):
    where = ActivityInvite.code_hash == family.hash_code(code) if code else ActivityInvite.id == invite_id
    row = db.execute(select(ActivityInvite).where(where).with_for_update()).scalar_one_or_none()
    if row is None:
        raise errors.not_found("找不到邀請，請確認邀請碼")
    group = db.execute(select(Group).where(Group.id == row.group_id).with_for_update()).scalar_one()
    now = datetime.now(timezone.utc)
    expires = row.expires_at.replace(tzinfo=timezone.utc) if row.expires_at.tzinfo is None else row.expires_at
    if action == "cancel":
        if group.created_by != me.id and row.inviter_id != me.id:
            raise errors.forbidden("你不能取消這份邀請")
    elif not code and row.invitee_id != me.id:
        raise errors.forbidden("這份邀請不是給你的")
    if row.status != "pending" or expires <= now:
        raise errors.conflict("邀請已使用、已取消或已過期")
    if action == "accept":
        if group.personal_owner_id is not None or group.removed_at or group.settled_at or group.archived_at:
            raise errors.conflict("這個活動已經結束或暫停使用")
        if crud.exists(GroupMember, {"group_id": group.id, "user_id": me.id}, db=db):
            raise errors.conflict("你已經在這個活動裡")
        crud.save(GroupMember, {"group_id": group.id, "user_id": me.id}, db=db)
    row.status = {"accept": "accepted", "decline": "declined", "cancel": "cancelled"}[action]
    row.responded_at = now
    if code:
        row.invitee_id = me.id
    db.flush()
    return {"id": str(row.id), "groupId": str(group.id), "groupName": group.name, "status": row.status}


def listing(db, me):
    owned = crud.find(Group, {"created_by": me.id, "personal_owner_id__isnull": True,
                              "removed_at__isnull": True}, fields="id", db=db)
    rows = crud.find(ActivityInvite, {"status": "pending", "expires_at__gt": datetime.now(timezone.utc),
                                     "or": [{"invitee_id": me.id}, {"group_id__in": owned}]}, order_by="-id", db=db)
    groups = {g.id: g for g in crud.find(Group, {"id__in": {r.group_id for r in rows},
                                                 "removed_at__isnull": True, "settled_at__isnull": True,
                                                 "archived_at__isnull": True}, db=db)}
    return {"invites": [{"id": str(r.id), "groupId": str(r.group_id), "groupName": groups[r.group_id].name,
                         "incoming": r.invitee_id == me.id, "label": r.label or "朋友",
                         "kind": "code" if r.code_hash else "account", "expiresAt": r.expires_at.isoformat()}
                        for r in rows if r.group_id in groups]}
