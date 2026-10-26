"""鈴鐺裡「等你決定的事」：有人邀你加入家庭、加入活動。

用帳號邀請時才會有收件人（邀請碼是當面或私訊傳的，系統不知道給了誰）。
記帳類（toolkit/notify.py）、零用金（services/allowance_ledger.py）、
活動目標金額（services/activity_target.py）、預算門檻（GET /api/notifications）各自在自己的地方寫。
所有改動由呼叫者一起 commit。
"""
from __future__ import annotations

from app.models import Family, Notification, User
from app.toolkit import crud


def _name(db, user_id) -> str:
    return crud.get(User, user_id, fields="display_name", db=db) or ""


def family_invite(db, invite) -> None:
    family = crud.get(Family, invite.family_id, fields="name", db=db) or ""
    crud.save(Notification, {"recipient_id": invite.invitee_id, "actor_id": invite.inviter_id,
                             "type": "family_invite", "payload_json": {
                                 "inviteId": str(invite.id), "familyName": family, "role": invite.role,
                                 "inviterName": _name(db, invite.inviter_id)}}, db=db)


def activity_invite(db, invite, group) -> None:
    crud.save(Notification, {"recipient_id": invite.invitee_id, "actor_id": invite.inviter_id,
                             "type": "activity_invite", "payload_json": {
                                 "inviteId": str(invite.id), "groupId": str(group.id), "groupName": group.name,
                                 "inviterName": _name(db, invite.inviter_id)}}, db=db)
