"""活動的期間：開始日（預設今天、可以自己選）與結束日（選填）。

規則（使用者 10/27 定的）：
    開始日可以比今天早，也可以比今天晚
    結束日不能比今天早——整段期間都已經過去的活動，要重新設定日期
    結束日一定要在開始日之後
    開始日比今天晚＝預先規劃的活動：先不放進活動選單，到了開始日才放上去，並通知每一位成員

舊的活動沒有開始日（starts_on 是 NULL），就當成建立的那一天。
guards.current_user 每次請求呼叫 notify_started；系統沒有排程器，到了開始日由有人打開系統時補上通知。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import or_, update

from app.models import Group, GroupMember, Notification
from app.toolkit import crud, errors

TW = timezone(timedelta(hours=8))


def today() -> date:
    return datetime.now(TW).date()


def parse(value: str | None, label: str) -> date | None:
    """空的回 None；格式不對回 422。"""
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise errors.unprocessable(label + "要是 YYYY-MM-DD") from None


def check(starts_on: date, ends_on: date | None) -> None:
    """沒有結束日就一直記下去，什麼都不用比。"""
    if ends_on is None:
        return
    if ends_on < today():
        raise errors.bad_request("結束日已經過了，整段期間都在今天以前，請重新設定日期")
    if ends_on <= starts_on:
        raise errors.bad_request("結束日要在開始日之後")


def created_day(group) -> date:
    at = group.created_at if group.created_at.tzinfo else group.created_at.replace(tzinfo=timezone.utc)
    return at.astimezone(TW).date()


def start_of(group) -> date:
    return group.starts_on or created_day(group)


def planned(group, on: date | None = None) -> bool:
    """預先規劃、還沒到開始日：不放進活動選單。"""
    return group.starts_on is not None and group.starts_on > (on or today())


def notify_started(db, user) -> None:
    """預先規劃的活動到了開始日：通知這位成員一次（開始日改過、再到一次會再通知）。

    ⚠️ 打開頁面時會同時進來好幾個請求，每個都會跑這裡。先讀再寫會讓每個請求都以為還沒通知過，
       所以用帶條件的 UPDATE 搶 group_members.start_notified_on：搶到（改到一列）的那個才發通知。
    """
    marks = {m.group_id: m.start_notified_on for m in crud.find(GroupMember, {"user_id": user.id}, db=db)}
    if not marks:
        return
    on = today()
    started = [g for g in crud.find(Group, {"id__in": list(marks), "starts_on__lte": on, "personal_owner_id__isnull": True,
                                             "removed_at__isnull": True, "settled_at__isnull": True}, db=db)
               if g.starts_on > created_day(g)                  # 建立當天就開始的，本來就在選單裡，不用通知
               and marks[g.id] != g.starts_on]
    for g in started:
        won = db.execute(update(GroupMember)
                         .where(GroupMember.group_id == g.id, GroupMember.user_id == user.id,
                                or_(GroupMember.start_notified_on.is_(None), GroupMember.start_notified_on != g.starts_on))
                         .values(start_notified_on=g.starts_on)).rowcount
        if not won:                                             # 同一時間另一個請求已經通知了
            continue
        crud.save(Notification, {"recipient_id": user.id, "type": "activity_start", "payload_json": {
            "groupId": str(g.id), "groupName": g.name, "startsOn": g.starts_on.isoformat(),
            "endsOn": g.ends_on.isoformat() if g.ends_on else None}}, db=db)
        db.commit()
