"""個人大帳本與逐人合併。所有改動由呼叫者一起 commit。"""
from datetime import datetime, timezone

from sqlalchemy import select

from app import catalog
from app.models import AuditLog, Group, GroupMember, NlpParse, Transaction, User
from app.toolkit import crud, errors


def ensure_personal(db, user):
    # 同一個人的不同帳本同時合併，也只會建立一本大帳本。
    db.execute(select(User).where(User.id == user.id).with_for_update()).scalar_one()
    personal = crud.get(Group, where={"personal_owner_id": user.id}, db=db)
    if personal is None:
        personal = crud.save(Group, {
            "name": user.display_name[:17] + "的帳本", "color": catalog.GROUP_COLORS[0],
            "created_by": user.id, "personal_owner_id": user.id, "kind": "standing",
        }, db=db)
        crud.save(GroupMember, {"group_id": personal.id, "user_id": user.id}, db=db)
    return personal


def merge_personal(db, group, me):
    # 先鎖原帳本，再重新檢查成員資格，避免重複提交或兩位成員同時退出。
    group = db.execute(select(Group).where(Group.id == group.id).with_for_update()
                       .execution_options(populate_existing=True)).scalar_one()
    if group.removed_at is not None:
        raise errors.not_found("找不到這本帳")
    if not crud.exists(GroupMember, {"group_id": group.id, "user_id": me.id}, db=db):
        raise errors.forbidden("你不在這本帳裡")
    if group.personal_owner_id is not None:
        raise errors.bad_request("個人大帳本不能合併或退出")

    personal = ensure_personal(db, me)
    originals = crud.find(Transaction, {
        "group_id": group.id, "user_id": me.id, "is_snapshot": False,
    }, order_by="id", db=db)
    copies = []
    for original in originals:
        copied = copy_to_personal(db, original, personal.id)
        copies.append({"originalId": str(original.id), "copyId": str(copied.id)})
    crud.remove(GroupMember, {"group_id": group.id, "user_id": me.id}, db=db)
    remaining = crud.find(GroupMember, {"group_id": group.id},
                          order_by=("joined_at", "user_id"), db=db)
    now = datetime.now(timezone.utc)
    if remaining:
        # 開帳者也能退出；交給最早加入的成員繼續管理。
        changes = {"settled_at": None}
        if group.created_by == me.id:
            changes["created_by"] = remaining[0].user_id
        crud.save(Group, {"id": group.id, **changes}, db=db)
    else:
        crud.save(Group, {"id": group.id, "settled_at": now, "removed_at": now}, db=db)
    crud.save(AuditLog, {
        "actor_id": me.id, "action": "merge_group", "target_type": "group", "target_id": group.id,
        "meta_json": {"personalGroupId": str(personal.id), "copied": len(copies),
                      "copies": copies, "closed": not remaining},
    }, db=db)
    return {"id": str(group.id), "personalGroupId": str(personal.id), "copied": len(copies),
            "closed": not remaining, "settledAt": now.isoformat() if not remaining else None}


def copy_to_personal(db, original, personal_id):
    """保留原帳本的歷史，建立獨立的個人副本；同一原始紀錄不重複複製。"""
    copied = crud.get(Transaction, where={"copied_from_id": original.id}, db=db)
    if copied is None:
        values = {c.name: getattr(original, c.name) for c in Transaction.__table__.columns
                  if c.name not in {"id", "group_id", "is_snapshot", "copied_from_id"}}
        copied = crud.save(Transaction, {**values, "group_id": personal_id,
                                        "copied_from_id": original.id, "is_snapshot": False}, db=db)
        for parsed in crud.find(NlpParse, {"transaction_id": original.id}, db=db):
            values = {c.name: getattr(parsed, c.name) for c in NlpParse.__table__.columns
                      if c.name not in {"id", "transaction_id"}}
            crud.save(NlpParse, {**values, "transaction_id": copied.id}, db=db)
    crud.save(Transaction, {"id": original.id, "is_snapshot": True}, db=db)
    return copied
