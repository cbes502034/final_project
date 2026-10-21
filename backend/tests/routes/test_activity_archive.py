"""活動邀請、來源搜尋、跨年包裹；驗證家庭關係不受活動邀請影響。"""
from datetime import datetime, timedelta, timezone

import pytest

from app.models import ActivityInvite, FamilyMember, GroupMember, Transaction
from app.toolkit import crud
from tests.routes.conftest import PASSWORD, categories, family_of, ledger_of, login, now, spend, user


@pytest.mark.route("POST", "/api/groups/{gid}/invites")
def test_friends_join_by_code_or_account_without_changing_families(api):
    owner, friend, second, stranger = [user(f"{n}@x.tw", n) for n in ("owner", "friend", "second", "stranger")]
    family_of((owner, "parent"))
    other_family = family_of((friend, "parent"))
    activity = ledger_of(owner, name="朋友聚餐")
    cats = categories()
    shared = spend(owner, activity, cats["餐飲"], 200)
    private = ledger_of(owner, name="私人", personal_owner_id=owner.id)
    spend(owner, private, cats["餐飲"], 999)
    created = api.post(f"/api/groups/{activity.id}/invites", headers=login(owner), json={"label": "給朋友"})
    assert created.status_code == 200, created.text
    code = created.json()["code"]
    row = crud.get(ActivityInvite, int(created.json()["id"]))
    assert row.code_hash and row.code_hash != code
    accepted = api.post("/api/group-invites/join", headers=login(friend), json={"code": code.lower()})
    assert accepted.status_code == 200, accepted.text
    assert crud.exists(GroupMember, {"group_id": activity.id, "user_id": friend.id})
    assert crud.get(FamilyMember, where={"user_id": friend.id}).family_id == other_family.id
    visible = api.get(f"/api/transactions?groupId={activity.id}", headers=login(friend)).json()
    assert [t["id"] for t in visible["transactions"]] == [str(shared.id)]
    assert visible["transactions"][0]["userName"] == owner.display_name
    assert api.get(f"/api/transactions?groupId={private.id}", headers=login(friend)).status_code == 403
    assert api.post("/api/group-invites/join", headers=login(second), json={"code": code}).status_code == 409

    invited = api.post(f"/api/groups/{activity.id}/invites", headers=login(owner), json={"email": second.email})
    assert invited.status_code == 200 and invited.json()["code"] is None
    iid = invited.json()["id"]
    inbox = api.get("/api/group-invites", headers=login(second)).json()["invites"]
    assert inbox[0]["incoming"] and inbox[0]["groupName"] == activity.name
    assert api.post(f"/api/group-invites/{iid}", headers=login(stranger), json={"action": "accept"}).status_code == 403
    assert api.post(f"/api/group-invites/{iid}", headers=login(second), json={"action": "accept"}).status_code == 200
    assert not crud.exists(FamilyMember, {"user_id": second.id})
    assert api.post(f"/api/groups/{activity.id}/invites", headers=login(friend), json={}).status_code == 403


@pytest.mark.route("POST", "/api/groups/{gid}/invites")
def test_activity_invites_expire_and_can_be_cancelled(api):
    owner, friend = user("o@x.tw", "建立者"), user("f@x.tw", "朋友")
    activity = ledger_of(owner)
    created = api.post(f"/api/groups/{activity.id}/invites", headers=login(owner), json={}).json()
    crud.save(ActivityInvite, {"id": int(created["id"]), "expires_at": now() - timedelta(seconds=1)})
    assert api.post("/api/group-invites/join", headers=login(friend), json={"code": created["code"]}).status_code == 409
    invitation = api.post(f"/api/groups/{activity.id}/invites", headers=login(owner), json={}).json()
    assert api.post(f"/api/group-invites/{invitation['id']}", headers=login(owner), json={"action": "cancel"}).status_code == 200
    assert api.post("/api/group-invites/join", headers=login(friend), json={"code": invitation["code"]}).status_code == 409


@pytest.mark.route("GET", "/api/transactions/archive")
def test_year_month_packages_and_activity_search_include_copied_origins(api):
    me, friend = user("me@x.tw", "本人"), user("f@x.tw", "朋友")
    personal = ledger_of(me, name="本人的帳本", personal_owner_id=me.id)
    activity = ledger_of(friend, me, name="沖繩旅行")
    cat = categories()["餐飲"]
    spend(me, personal, cat, 1, day="2024-02-29")
    spend(me, personal, cat, 2, day="2025-12-31")
    spend(me, personal, cat, 3, day="2026-01-01")
    original = spend(me, activity, cat, 100, day="2025-12-30", merchant="餐廳")
    assert api.post(f"/api/groups/{activity.id}/settle", headers=login(me)).status_code == 200
    copied = crud.get(Transaction, where={"copied_from_id": original.id})
    assert copied.origin_group_id == activity.id
    archived = api.get(f"/api/transactions/archive?groupId={personal.id}", headers=login(me))
    assert archived.status_code == 200, archived.text
    body = archived.json()
    assert [y["year"] for y in body["years"]] == ["2026", "2025", "2024"]
    assert body["years"][1]["months"] == [{"month": "2025-12", "count": 2, "packed": True}]
    assert "+08:00" in body["nextPackAt"] and body["nextPackAt"][8:10] == "01"
    assert body["activities"] == [{"id": str(activity.id), "name": activity.name}]
    found = api.get(f"/api/transactions?groupId={personal.id}&q=沖繩", headers=login(me)).json()
    assert found["total"] == 1 and found["transactions"][0]["activityName"] == activity.name
    filtered = api.get(f"/api/transactions/archive?groupId={personal.id}&activityId={activity.id}", headers=login(me)).json()
    assert filtered["years"] == [{"year": "2025", "months": [{"month": "2025-12", "count": 1, "packed": True}]}]
    assert api.get(f"/api/transactions/archive?groupId={personal.id}", headers=login(friend)).status_code == 403


@pytest.mark.route("GET", "/api/transactions/archive")
@pytest.mark.parametrize("instant,current,next_pack,packed", [
    ("2026-12-31T15:59:59+00:00", "2026-12", "2027-01-01T00:00:00+08:00", False),
    ("2026-12-31T16:00:00+00:00", "2027-01", "2027-02-01T00:00:00+08:00", True),
    ("2024-02-28T16:00:00+00:00", "2024-02", "2024-03-01T00:00:00+08:00", False),
    ("2024-02-29T16:00:00+00:00", "2024-03", "2024-04-01T00:00:00+08:00", True),
])
def test_packages_roll_over_at_taipei_midnight_including_leap_year(api, monkeypatch, instant, current, next_pack, packed):
    import inspect
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.fromisoformat(instant).astimezone(tz or timezone.utc)
    endpoint = next(r.endpoint for r in api.app.routes if getattr(r, "path", None) == "/api/transactions/archive")
    monkeypatch.setitem(inspect.unwrap(endpoint).__globals__, "datetime", Clock)
    me = user("time@x.tw", "本人")
    personal = ledger_of(me, personal_owner_id=me.id)
    spend(me, personal, categories()["餐飲"], 1, day="2024-02-29" if instant.startswith("2024") else "2026-12-31")
    body = api.get(f"/api/transactions/archive?groupId={personal.id}", headers=login(me)).json()
    assert body["currentMonth"] == current
    assert body["nextPackAt"] == next_pack
    assert body["years"][0]["months"][0]["packed"] is packed


@pytest.mark.route("DELETE", "/api/auth/me")
def test_deleted_activity_owner_does_not_break_others_origin_history(api):
    me, friend = user("owner@x.tw", "建立者"), user("friend@x.tw", "朋友")
    activity = ledger_of(me, friend, name="共同旅行")
    spend(friend, activity, categories()["餐飲"], 50)
    assert api.post(f"/api/groups/{activity.id}/settle", headers=login(friend)).status_code == 200
    assert api.post(f"/api/groups/{activity.id}/settle", headers=login(me)).status_code == 200
    assert api.request("DELETE", "/api/auth/me", headers=login(me), json={"password": PASSWORD}).status_code == 200
    found = api.get("/api/transactions?q=共同旅行", headers=login(friend)).json()
    assert found["total"] == 1 and found["transactions"][0]["activityName"] == "共同旅行"
