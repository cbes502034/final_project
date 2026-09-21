"""家庭、邀請、監管、零用金、稽核、通知（成員4）。怎麼跑、兩種對象的差別：看 conftest.py 的檔頭。"""

from datetime import timedelta

import pytest

from app.models import (
    AlertRule, Allowance, AuditLog, Family, FamilyInvite, FamilyMember, Group, GroupMember, Guardianship,
    Notification, Transaction,
)
from app.toolkit import crud, family
from tests.routes.conftest import (
    categories, family_of, goal, guard, ledger_of, login, now, spend, this_month, user,
)


def _code(fam, inviter, role="child", **extra):
    """直接在資料庫放一組邀請碼，回傳明碼。"""
    code = family.new_code()
    crud.save(FamilyInvite, {"family_id": fam.id, "inviter_id": inviter.id, "code_hash": family.hash_code(code),
                             "role": role, "expires_at": now() + timedelta(days=7), **extra})
    return code


def _invite(fam, inviter, invitee, role="child", **extra):
    return crud.save(FamilyInvite, {"family_id": fam.id, "inviter_id": inviter.id, "invitee_id": invitee.id,
                                    "role": role, "expires_at": now() + timedelta(days=7), **extra})


def _role(u):
    return crud.get(FamilyMember, where={"user_id": u.id, "status": "active"}, fields="role")


# ===========================================================================
# GET /api/family
# ===========================================================================
FAM = ("GET", "/api/family")


@pytest.mark.route(*FAM)
def test_get_family_看得到的人才有存款目標(api):
    dad, mom, kid, kid2, aunt = (user(e, n, birth_year=y) for e, n, y in (
        ("d@x.tw", "爸爸", 1974), ("m@x.tw", "媽媽", None), ("k@x.tw", "小華", 2010),
        ("k2@x.tw", "小安", None), ("a@x.tw", "阿姨", None)))
    fam = family_of((dad, "parent"), (mom, "parent"), (kid, "child"), (kid2, "child"))
    user("admin@x.tw", "管理員", is_platform_admin=True)
    gs = guard(dad, kid)
    ledger_of(dad, aunt)
    for who in (dad, mom, kid, kid2):
        goal(who, 1000)
    r = api.get("/api/family", headers=login(dad))
    assert r.status_code == 200, r.text
    b = r.json()
    assert (b["me"], b["myRole"], b["family"]) == (str(dad.id), "parent",
                                                    {"id": str(fam.id), "name": "王家", "createdBy": str(dad.id)})
    assert b["visible"] == [str(dad.id), str(mom.id), str(kid.id)]
    assert b["queryable"] == [str(dad.id), str(mom.id), str(kid.id), str(aunt.id)]
    cards = {m["name"]: m for m in b["members"]}
    assert set(cards) == {"爸爸", "媽媽", "小華", "小安"}
    assert "savingsGoal" in cards["媽媽"] and "savingsGoal" in cards["小華"] and "savingsGoal" not in cards["小安"]
    assert cards["爸爸"]["age"] > 50 and cards["媽媽"]["age"] is None and cards["爸爸"]["avatar"] == "爸"
    assert cards["小華"]["role"] == "child" and cards["小華"]["familyId"] == str(fam.id)
    assert b["guardianships"] == [{"id": str(gs.id), "guardian": str(dad.id), "ward": str(kid.id),
                                   "since": gs.since.date().isoformat(), "scope": gs.scope,
                                   "guardianName": "爸爸", "wardName": "小華"}]
    assert [x["id"] for x in b["roles"]] == ["master", "parent", "child"] and len(b["permissions"]) == 25
    kb = api.get("/api/family", headers=login(kid)).json()
    assert [m["name"] for m in kb["members"] if "savingsGoal" in m] == ["小華"]
    assert len(kb["guardianships"]) == 1                                  # 被照看的人看得到誰在看


@pytest.mark.route(*FAM)
def test_get_family_沒有家庭_只有自己(api):
    me = user("l@x.tw", "阿明")
    b = api.get("/api/family", headers=login(me)).json()
    assert b["family"] is None and b["myRole"] is None and b["guardianships"] == []
    assert [m["id"] for m in b["members"]] == [str(me.id)] and b["visible"] == [str(me.id)]


# ===========================================================================
# POST /api/family、DELETE /api/family
# ===========================================================================
NEWFAM = ("POST", "/api/family")
DISSOLVE = ("DELETE", "/api/family")


@pytest.mark.route(*NEWFAM)
def test_create_family(api):
    me = user("l@x.tw", "阿明")
    other = user("o@x.tw", "阿華")
    old = family_of((other, "parent"), name="舊家")
    crud.save(FamilyMember, {"family_id": old.id, "user_id": me.id, "role": "child", "status": "removed"})
    r = api.post("/api/family", headers=login(me), json={"name": "  林  家 "})
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["role"] == "parent" and b["family"]["name"] == "林 家" and b["family"]["createdBy"] == str(me.id)
    assert _role(me) == "parent"
    assert crud.exists(AuditLog, {"action": "create_family", "actor_id": me.id})
    assert api.post("/api/family", headers=login(me), json={"name": "又一家"}).status_code == 409
    assert api.post("/api/family", headers=login(user("n@x.tw", "新人")), json={"name": "   "}).status_code == 422
    admin = user("admin@x.tw", "管理員", is_platform_admin=True)
    assert api.post("/api/family", headers=login(admin), json={"name": "管理員家"}).status_code == 403


@pytest.mark.route(*DISSOLVE)
def test_dissolve_family_收掉關係_紀錄不刪(api):
    dad, kid, outsider = user("d@x.tw", "爸爸"), user("k@x.tw", "小華"), user("o@x.tw", "外人")
    fam = family_of((dad, "parent"), (kid, "child"))
    guard(dad, kid)
    crud.save(Allowance, {"payer_id": dad.id, "ward_id": kid.id, "amount": 3000})
    cats = categories()
    g = ledger_of(dad, kid)
    spend(kid, g, cats["餐飲"], 50)
    _code(fam, dad)
    _invite(fam, dad, outsider)
    r = api.delete("/api/family", headers=login(dad))
    assert r.status_code == 200, r.text
    assert r.json() == {"dissolved": True, "family": {"id": str(fam.id), "name": "王家"}, "released": 2}
    assert crud.count(FamilyMember, {"status": "active"}) == 0
    assert crud.get(Guardianship, where={"ward_id": kid.id}).ended_at is not None
    assert int(crud.get(Allowance, where={"ward_id": kid.id}).amount) == 0
    assert [m.user_id for m in crud.find(GroupMember, {"group_id": g.id})] == [dad.id]
    assert set(crud.find(FamilyInvite, fields="status")) == {"cancelled"}
    assert crud.count(Transaction) == 1
    assert crud.exists(AuditLog, {"action": "dissolve_family"})


@pytest.mark.route(*DISSOLVE)
def test_dissolve_family_還有別的家長_或不是家長(api):
    dad, mom, kid = user("d@x.tw", "爸爸"), user("m@x.tw", "媽媽"), user("k@x.tw", "小華")
    family_of((dad, "parent"), (mom, "parent"), (kid, "child"))
    assert api.delete("/api/family", headers=login(dad)).status_code == 409
    assert api.delete("/api/family", headers=login(kid)).status_code == 403
    assert crud.count(FamilyMember, {"status": "active"}) == 3


# ===========================================================================
# 邀請碼
# ===========================================================================
CODE = ("POST", "/api/family/invite")
JOIN = ("POST", "/api/family/join")


@pytest.mark.route(*CODE)
def test_create_invite_code_只存雜湊_同身分舊碼作廢(api):
    dad, kid = user("d@x.tw", "爸爸"), user("k@x.tw", "小華")
    family_of((dad, "parent"), (kid, "child"))
    r = api.post("/api/family/invite", headers=login(dad), json={"role": "child"})
    assert r.status_code == 201, r.text
    first = r.json()
    assert first["role"] == "child" and len(first["code"]) == 9 and first["code"][4] == "-" and first["expiresAt"]
    row = crud.get(FamilyInvite, where={"code_hash__isnull": False})
    assert row.code_hash == family.hash_code(first["code"]) and first["code"] not in row.code_hash
    api.post("/api/family/invite", headers=login(dad), json={"role": "parent"})
    api.post("/api/family/invite", headers=login(dad), json={"role": "child"})
    statuses = [(i.role, i.status) for i in crud.find(FamilyInvite, order_by="id")]
    assert statuses == [("child", "cancelled"), ("parent", "pending"), ("child", "pending")]
    assert api.post("/api/family/invite", headers=login(kid), json={"role": "child"}).status_code == 403
    assert api.post("/api/family/invite", headers=login(dad), json={"role": "boss"}).status_code == 422


@pytest.mark.route(*JOIN)
def test_join_family_照碼上的身分加入_只能用一次(api):
    dad, me, late = user("d@x.tw", "爸爸"), user("l@x.tw", "阿明"), user("t@x.tw", "晚到")
    fam = family_of((dad, "parent"))
    other = family_of((user("o@x.tw", "別家"), "parent"), name="林家")
    crud.save(FamilyMember, {"family_id": other.id, "user_id": me.id, "role": "child", "status": "removed"})
    code = _code(fam, dad, role="parent")
    r = api.post("/api/family/join", headers=login(me), json={"code": " " + code.lower().replace("-", " ")})
    assert r.status_code == 200, r.text
    assert r.json() == {"family": {"id": str(fam.id), "name": "王家"}, "role": "parent"}
    assert _role(me) == "parent"
    assert crud.get(FamilyInvite, where={"code_hash": family.hash_code(code)}).status == "accepted"
    r = api.post("/api/family/join", headers=login(late), json={"code": code})
    assert r.status_code == 400 and "用過" in r.json()["detail"]
    assert api.post("/api/family/join", headers=login(me), json={"code": code}).status_code == 409
    assert api.post("/api/family/join", headers=login(late), json={"code": "ABCD"}).status_code == 400
    assert api.post("/api/family/join", headers=login(late), json={"code": "ZZZZ-ZZZZ"}).status_code == 404


@pytest.mark.route(*JOIN)
def test_join_family_過期_作廢_沒有家長(api):
    dad, kid, me = user("d@x.tw", "爸爸"), user("k@x.tw", "小華"), user("l@x.tw", "阿明")
    fam = family_of((dad, "parent"), (kid, "child"))
    expired = _code(fam, dad, expires_at=now() - timedelta(minutes=1))
    cancelled = _code(fam, dad, status="cancelled")
    r = api.post("/api/family/join", headers=login(me), json={"code": expired})
    assert r.status_code == 400 and "過期" in r.json()["detail"]
    r = api.post("/api/family/join", headers=login(me), json={"code": cancelled})
    assert r.status_code == 400 and "取消" in r.json()["detail"]
    ok = _code(fam, dad)
    crud.save(FamilyMember, {"status": "removed"}, where={"user_id": dad.id})
    assert api.post("/api/family/join", headers=login(me), json={"code": ok}).status_code == 409
    assert _role(me) is None


# ===========================================================================
# 用帳號找人、邀請
# ===========================================================================
LOOKUP = ("GET", "/api/family/lookup")
INVITES = ("GET", "/api/family/invites")
SEND = ("POST", "/api/family/invites")
ACCEPT = ("POST", "/api/family/invites/{invite_id}/accept")
DECLINE = ("DELETE", "/api/family/invites/{invite_id}")


@pytest.mark.route(*LOOKUP)
def test_lookup_user_四種狀態_不回財務資料(api):
    dad, kid = user("d@x.tw", "爸爸"), user("k@x.tw", "小華")
    free, busy, invited = user("f@x.tw", "自由"), user("b@x.tw", "別家的"), user("i@x.tw", "邀過的")
    admin = user("admin@x.tw", "管理員", is_platform_admin=True)
    fam = family_of((dad, "parent"), (kid, "child"))
    family_of((busy, "parent"), name="林家")
    _invite(fam, dad, invited)
    h = login(dad)
    got = lambda e: api.get("/api/family/lookup?email=" + e, headers=h).json()  # noqa: E731
    assert got("F@X.TW") == {"user": {"id": str(free.id), "name": "自由", "avatar": "由", "avatarUrl": None},
                             "status": "available"}
    assert got("k@x.tw")["status"] == "member"
    assert got("b@x.tw")["status"] == "unavailable"
    assert got("i@x.tw")["status"] == "invited"
    assert got("admin@x.tw")["status"] == "unavailable" and admin
    assert api.get("/api/family/lookup?email=nobody@x.tw", headers=h).status_code == 404
    assert api.get("/api/family/lookup?email=abc", headers=h).status_code == 400
    assert api.get("/api/family/lookup", headers=h).status_code == 400
    assert api.get("/api/family/lookup?email=f@x.tw", headers=login(kid)).status_code == 403


@pytest.mark.route(*LOOKUP)
def test_lookup_user_一分鐘超過十次回_429(api):
    dad = user("d@x.tw", "爸爸")
    family_of((dad, "parent"))
    codes = [api.get("/api/family/lookup?email=x%d@x.tw" % i, headers=login(dad)).status_code for i in range(11)]
    assert codes == [404] * 10 + [429]
    assert crud.count(AuditLog, {"action": "lookup_user"}) == 10


@pytest.mark.route(*INVITES)
def test_list_invites_三份清單(api):
    dad, kid, guest = user("d@x.tw", "爸爸"), user("k@x.tw", "小華"), user("g@x.tw", "客人")
    fam = family_of((dad, "parent"), (kid, "child"))
    inv = _invite(fam, dad, guest, role="parent")
    _invite(fam, dad, user("e@x.tw", "過期的"), expires_at=now() - timedelta(days=1))
    _code(fam, dad, role="parent")
    b = api.get("/api/family/invites", headers=login(guest)).json()
    assert b["received"] == [{"id": str(inv.id), "familyName": "王家", "inviterName": "爸爸", "role": "parent",
                              "expiresAt": b["received"][0]["expiresAt"]}]
    assert b["sent"] == [] and b["codes"] == []
    b = api.get("/api/family/invites", headers=login(dad)).json()
    assert b["received"] == []
    assert [(s["id"], s["name"], s["email"], s["avatar"], s["role"]) for s in b["sent"]] == \
        [(str(inv.id), "客人", "g@x.tw", "人", "parent")]
    assert [(c["code"], c["role"]) for c in b["codes"]] == [(None, "parent")]
    b = api.get("/api/family/invites", headers=login(kid)).json()
    assert b == {"received": [], "sent": [], "codes": []}


@pytest.mark.route(*SEND)
def test_send_invite(api):
    dad, kid, free, busy = user("d@x.tw", "爸爸"), user("k@x.tw", "小華"), user("f@x.tw", "自由"), user("b@x.tw", "別家的")
    fam = family_of((dad, "parent"), (kid, "child"))
    family_of((busy, "parent"), name="林家")
    h = login(dad)
    r = api.post("/api/family/invites", headers=h, json={"userId": str(free.id), "role": "child"})
    assert r.status_code == 201, r.text
    row = crud.get(FamilyInvite, int(r.json()["id"]))
    assert r.json()["status"] == "pending" and (row.family_id, row.invitee_id, row.role) == (fam.id, free.id, "child")
    assert crud.exists(AuditLog, {"action": "invite_member", "target_id": free.id})
    assert api.post("/api/family/invites", headers=h, json={"userId": str(free.id), "role": "child"}).status_code == 409
    assert api.post("/api/family/invites", headers=h, json={"userId": str(busy.id), "role": "child"}).status_code == 400
    assert api.post("/api/family/invites", headers=h, json={"userId": "99999", "role": "child"}).status_code == 404
    assert api.post("/api/family/invites", headers=login(kid),
                    json={"userId": str(free.id), "role": "child"}).status_code == 403


@pytest.mark.route(*ACCEPT)
def test_accept_invite(api):
    dad, guest, stranger = user("d@x.tw", "爸爸"), user("g@x.tw", "客人"), user("s@x.tw", "路人")
    fam = family_of((dad, "parent"))
    inv = _invite(fam, dad, guest)
    old = _invite(fam, dad, stranger, expires_at=now() - timedelta(minutes=1))
    assert api.post("/api/family/invites/%d/accept" % inv.id, headers=login(stranger)).status_code == 404
    r = api.post("/api/family/invites/%d/accept" % old.id, headers=login(stranger))
    assert r.status_code == 400 and "過期" in r.json()["detail"]
    r = api.post("/api/family/invites/%d/accept" % inv.id, headers=login(guest))
    assert r.status_code == 200, r.text
    assert r.json() == {"family": {"id": str(fam.id), "name": "王家"}, "role": "child"}
    assert _role(guest) == "child" and crud.get(FamilyInvite, inv.id).status == "accepted"
    assert api.post("/api/family/invites/%d/accept" % inv.id, headers=login(guest)).status_code == 409
    lonely = family_of((user("x@x.tw", "走掉的家長"), "parent"), name="空家")
    crud.save(FamilyMember, {"status": "removed"}, where={"family_id": lonely.id})
    orphan = _invite(lonely, dad, stranger)
    assert api.post("/api/family/invites/%d/accept" % orphan.id, headers=login(stranger)).status_code == 409


@pytest.mark.route(*DECLINE)
def test_decline_invite(api):
    dad, kid, guest, guest2 = user("d@x.tw", "爸爸"), user("k@x.tw", "小華"), user("g@x.tw", "客人"), user("h@x.tw", "客人二")
    fam = family_of((dad, "parent"), (kid, "child"))
    a, b = _invite(fam, dad, guest), _invite(fam, dad, guest2)
    assert api.delete("/api/family/invites/%d" % a.id, headers=login(kid)).status_code == 403
    r = api.delete("/api/family/invites/%d" % a.id, headers=login(guest))
    assert r.status_code == 200 and r.json() == {"id": str(a.id), "status": "declined"}
    r = api.delete("/api/family/invites/%d" % b.id, headers=login(dad))
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    assert crud.count(FamilyInvite) == 2
    assert api.delete("/api/family/invites/%d" % a.id, headers=login(guest)).status_code == 404


# ===========================================================================
# 改角色、移出與退出
# ===========================================================================
ROLE = ("PATCH", "/api/family/members/{user_id}")
REMOVE = ("DELETE", "/api/family/members/{user_id}")


@pytest.mark.route(*ROLE)
def test_change_member_role(api):
    dad, mom, kid, stranger = user("d@x.tw", "爸爸"), user("m@x.tw", "媽媽"), user("k@x.tw", "小華"), user("s@x.tw", "路人")
    family_of((dad, "parent"), (kid, "child"))
    family_of((stranger, "parent"), (mom, "parent"), name="林家")
    gk = guard(dad, kid)
    crud.save(Allowance, {"payer_id": dad.id, "ward_id": kid.id, "amount": 3000})
    h = login(dad)
    assert api.patch("/api/family/members/%d" % stranger.id, headers=h, json={"role": "parent"}).status_code == 404
    r = api.patch("/api/family/members/%d" % dad.id, headers=h, json={"role": "child"})
    assert r.status_code == 409                                          # 唯一的家長
    r = api.patch("/api/family/members/%d" % kid.id, headers=h, json={"role": "parent"})
    assert r.status_code == 200 and r.json() == {"id": str(kid.id), "role": "parent", "changed": True}
    assert _role(kid) == "parent" and crud.get(Guardianship, gk.id).ended_at is not None
    assert int(crud.get(Allowance, where={"ward_id": kid.id}).amount) == 0
    assert crud.get(AuditLog, where={"action": "change_role"}).meta_json["note"] == "把小華設為家長"
    r = api.patch("/api/family/members/%d" % kid.id, headers=h, json={"role": "parent"})
    assert r.status_code == 200 and r.json()["changed"] is False
    assert api.patch("/api/family/members/%d" % kid.id, headers=h, json={"role": "child"}).status_code == 403
    assert api.patch("/api/family/members/%d" % kid.id, headers=h, json={"role": "boss"}).status_code == 422
    # 現在有兩位家長：爸爸可以把自己改成子女，他照看別人的關係一起結束
    other_kid = user("k2@x.tw", "小安")
    crud.save(FamilyMember, {"family_id": crud.get(FamilyMember, where={"user_id": dad.id}).family_id,
                             "user_id": other_kid.id, "role": "child"})
    g2 = guard(dad, other_kid)
    r = api.patch("/api/family/members/%d" % dad.id, headers=h, json={"role": "child"})
    assert r.status_code == 200 and r.json()["changed"] is True
    assert _role(dad) == "child" and crud.get(Guardianship, g2.id).ended_at is not None


@pytest.mark.route(*REMOVE)
def test_remove_member_家長移出子女_收掉關係(api):
    dad, mom, kid = user("d@x.tw", "爸爸"), user("m@x.tw", "媽媽"), user("k@x.tw", "小華")
    fam = family_of((dad, "parent"), (mom, "parent"), (kid, "child"))
    guard(dad, kid)
    guard(mom, kid)
    cats = categories()
    home = ledger_of(dad, kid, name="家用")
    kids = ledger_of(kid, dad, name="小華的")
    spend(kid, home, cats["餐飲"], 10)
    _code(fam, kid)                                 # 他產生的碼（理論上子女不能產生，這裡只測會被作廢）
    r = api.delete("/api/family/members/%d" % kid.id, headers=login(dad))
    assert r.status_code == 200, r.text
    assert r.json() == {"id": str(kid.id), "removed": True, "endedGuardianships": 2}
    assert _role(kid) is None and crud.count(FamilyMember, {"user_id": kid.id, "status": "removed"}) == 1
    assert not crud.exists(GroupMember, {"group_id": home.id, "user_id": kid.id})
    assert [m.user_id for m in crud.find(GroupMember, {"group_id": kids.id})] == [kid.id]
    assert crud.get(FamilyInvite, where={"inviter_id": kid.id}).status == "cancelled"
    assert crud.count(Transaction) == 1
    note = crud.get(AuditLog, where={"action": "remove_member"}).meta_json["note"]
    assert note == "把小華移出「王家」"
    assert api.delete("/api/family/members/%d" % mom.id, headers=login(dad)).status_code == 403
    assert api.delete("/api/family/members/%d" % dad.id, headers=login(dad)).status_code == 400
    assert api.delete("/api/family/members/99999", headers=login(dad)).status_code == 404
    assert api.delete("/api/family/members/%d" % dad.id, headers=login(mom)).status_code == 403


@pytest.mark.route(*REMOVE)
def test_remove_member_自己退出(api):
    dad, kid = user("d@x.tw", "爸爸"), user("k@x.tw", "小華")
    fam = family_of((dad, "parent"), (kid, "child"))
    assert api.delete("/api/family/members/me", headers=login(dad)).status_code == 409   # 唯一的家長
    r = api.delete("/api/family/members/me", headers=login(kid))
    assert r.status_code == 200 and r.json() == {"left": True, "family": {"id": str(fam.id), "name": "王家"}}
    assert _role(kid) is None
    assert crud.exists(AuditLog, {"action": "leave_family", "target_id": kid.id})
    r = api.delete("/api/family/members/me", headers=login(dad))                          # 只剩自己，可以走
    assert r.status_code == 200
    assert api.delete("/api/family/members/me", headers=login(dad)).status_code == 403    # 已經沒有家庭


# ===========================================================================
# 監管關係
# ===========================================================================
GS = ("GET", "/api/guardianships")
NEWGS = ("POST", "/api/guardianships")
ENDGS = ("DELETE", "/api/guardianships/{gid}")


@pytest.mark.route(*GS)
def test_list_guardianships_雙向可見(api):
    dad, mom, kid, stranger = user("d@x.tw", "爸爸"), user("m@x.tw", "媽媽"), user("k@x.tw", "小華"), user("s@x.tw", "路人")
    family_of((dad, "parent"), (mom, "parent"), (kid, "child"))
    a = guard(dad, kid)
    guard(mom, kid)
    crud.save(Guardianship, {"id": a.id, "ended_at": now()})
    b = crud.find(Guardianship, {"ended_at__isnull": True})[0]
    r = api.get("/api/guardianships", headers=login(dad))
    assert r.status_code == 200, r.text
    assert r.json() == {"guardianships": [{"id": str(b.id), "guardian": str(mom.id), "ward": str(kid.id),
                                           "since": b.since.date().isoformat(), "scope": b.scope, "mine": False}]}
    assert api.get("/api/guardianships", headers=login(kid)).json()["guardianships"][0]["guardian"] == str(mom.id)
    assert api.get("/api/guardianships", headers=login(stranger)).status_code == 403


@pytest.mark.route(*NEWGS)
def test_create_guardianship(api):
    dad, mom, kid, stranger = user("d@x.tw", "爸爸"), user("m@x.tw", "媽媽"), user("k@x.tw", "小華"), user("s@x.tw", "路人")
    family_of((dad, "parent"), (mom, "parent"), (kid, "child"))
    h = login(dad)
    r = api.post("/api/guardianships", headers=h, json={"wardId": str(kid.id)})
    assert r.status_code == 201, r.text
    b = r.json()
    assert (b["guardian"], b["ward"], b["mine"], b["guardianName"], b["wardName"]) == \
        (str(dad.id), str(kid.id), True, "爸爸", "小華")
    assert b["since"] and b["scope"] and crud.exists(AuditLog, {"action": "grant_guardianship"})
    assert api.post("/api/guardianships", headers=h, json={"wardId": str(kid.id)}).status_code == 409
    assert api.post("/api/guardianships", headers=h, json={"wardId": str(mom.id)}).status_code == 422
    assert api.post("/api/guardianships", headers=h, json={"wardId": str(stranger.id)}).status_code == 404
    r = api.post("/api/guardianships", headers=login(mom), json={"wardId": str(kid.id), "guardianId": str(dad.id)})
    assert r.status_code == 403
    assert api.post("/api/guardianships", headers=login(kid), json={"wardId": str(kid.id)}).status_code == 403
    assert api.post("/api/guardianships", headers=login(mom),
                    json={"wardId": str(kid.id), "guardianId": str(mom.id)}).status_code == 201


@pytest.mark.route(*ENDGS)
def test_end_guardianship(api):
    dad, mom, kid, stranger = user("d@x.tw", "爸爸"), user("m@x.tw", "媽媽"), user("k@x.tw", "小華"), user("s@x.tw", "路人")
    family_of((dad, "parent"), (mom, "parent"), (kid, "child"))
    family_of((stranger, "parent"), name="林家")
    a = guard(dad, kid)
    crud.save(Allowance, {"payer_id": dad.id, "ward_id": kid.id, "amount": 3000})
    assert api.delete("/api/guardianships/%d" % a.id, headers=login(kid)).status_code == 403
    assert api.delete("/api/guardianships/%d" % a.id, headers=login(stranger)).status_code == 403
    r = api.delete("/api/guardianships/%d" % a.id, headers=login(mom))              # 同一家的另一位家長
    assert r.status_code == 200 and r.json() == {"id": str(a.id), "ended": True}
    assert crud.get(Guardianship, a.id).ended_at is not None
    assert int(crud.get(Allowance, where={"ward_id": kid.id}).amount) == 0
    assert crud.get(AuditLog, where={"action": "end_guardianship"}).meta_json["note"] == "解除爸爸對小華的監管"
    assert api.delete("/api/guardianships/%d" % a.id, headers=login(dad)).status_code == 404
    b = guard(dad, kid)
    assert api.delete("/api/guardianships/%d" % b.id, headers=login(dad)).status_code == 200


# ===========================================================================
# 零用金、稽核
# ===========================================================================
ALLOWANCES = ("GET", "/api/allowances")
SETALLOW = ("PUT", "/api/allowance")
AUDIT = ("GET", "/api/audit")


@pytest.mark.route(*ALLOWANCES)
def test_list_allowances(api):
    dad, kid, kid2 = user("d@x.tw", "爸爸"), user("k@x.tw", "小華"), user("k2@x.tw", "小安")
    guard(dad, kid)
    guard(dad, kid2)
    crud.save(Allowance, {"payer_id": dad.id, "ward_id": kid.id, "amount": 3000})
    cats = categories()
    g = ledger_of(kid)
    spend(kid, g, cats["餐飲"], 100)
    spend(kid, g, cats["餐飲"], 50)
    spend(kid, g, cats["薪資"], 999)
    r = api.get("/api/allowances", headers=login(dad))
    assert r.status_code == 200, r.text
    assert r.json() == {"allowances": [
        {"wardId": str(kid.id), "wardName": "小華", "amount": 3000, "spent": 150},
        {"wardId": str(kid2.id), "wardName": "小安", "amount": 0, "spent": 0},
    ]}
    assert api.get("/api/allowances", headers=login(kid)).json() == {"allowances": []}


@pytest.mark.route(*SETALLOW)
def test_set_allowance(api):
    dad, kid, other = user("d@x.tw", "爸爸"), user("k@x.tw", "小華"), user("o@x.tw", "別人家小孩")
    family_of((dad, "parent"), (kid, "child"))
    guard(dad, kid)
    h = login(dad)
    r = api.put("/api/allowance", headers=h, json={"wardId": str(kid.id), "amount": 3000})
    assert r.status_code == 200 and r.json() == {"wardId": str(kid.id), "wardName": "小華", "amount": 3000}
    api.put("/api/allowance", headers=h, json={"wardId": str(kid.id), "amount": 3500})
    rows = crud.find(Allowance)
    assert len(rows) == 1 and int(rows[0].amount) == 3500 and rows[0].period_key is None
    assert api.put("/api/allowance", headers=h, json={"wardId": str(other.id), "amount": 1}).status_code == 403
    assert api.put("/api/allowance", headers=h, json={"wardId": str(kid.id), "amount": -1}).status_code == 422
    assert crud.count(Transaction) == 0                                    # 零用金是設定，不是一筆支出


@pytest.mark.route(*AUDIT)
def test_list_audit(api):
    admin = user("admin@x.tw", "管理員", is_platform_admin=True)
    dad = user("d@x.tw", "爸爸")
    crud.save(AuditLog, [
        {"actor_id": dad.id, "action": "create_family", "target_type": "family", "target_id": 1,
         "meta_json": {"note": "建立「王家」"}},
        {"actor_id": admin.id, "action": "suspend_user", "target_type": "user", "target_id": dad.id},
        {"actor_id": None, "action": "system"},
    ])
    r = api.get("/api/audit", headers=login(admin))
    assert r.status_code == 200, r.text
    logs = r.json()["logs"]
    assert [x["action"] for x in logs] == ["system", "suspend_user", "create_family"]
    assert logs[0]["actor"] is None and logs[0]["actorName"] is None and logs[0]["target"] is None
    assert (logs[1]["actorName"], logs[1]["target"], logs[1]["note"]) == ("管理員", str(dad.id), "")
    assert logs[2]["note"] == "建立「王家」" and logs[2]["at"].endswith(("+00:00", "Z"))
    assert api.get("/api/audit", headers=login(dad)).status_code == 403


# ===========================================================================
# 通知
# ===========================================================================
NOTES = ("GET", "/api/notifications")
READ = ("PATCH", "/api/notifications/{nid}")
READALL = ("PATCH", "/api/notifications")


def _note(to, **extra):
    return crud.save(Notification, {"recipient_id": to.id, "type": "ward_transaction", **extra})


@pytest.mark.route(*NOTES)
def test_list_notifications_since_unread_maxId(api):
    dad, kid, other = user("d@x.tw", "爸爸"), user("k@x.tw", "小華"), user("o@x.tw", "別人")
    cats = categories()
    g = ledger_of(kid)
    t = spend(kid, g, cats["餐飲"], 320, merchant="全家")
    n1 = _note(dad, actor_id=kid.id, transaction_id=t.id, payload_json={"reason": "guardian"})
    n2 = _note(dad, type="group_transaction", read_at=now())
    _note(other)
    h = login(dad)
    r = api.get("/api/notifications", headers=h)
    assert r.status_code == 200, r.text
    b = r.json()
    assert [x["id"] for x in b["notifications"]] == [str(n2.id), str(n1.id)]
    assert (b["unread"], b["maxId"]) == (1, str(n2.id))
    one = b["notifications"][1]
    assert one == {"id": str(n1.id), "type": "ward_transaction", "actorId": str(kid.id), "reason": "guardian",
                   "createdAt": one["createdAt"], "readAt": None, "txId": str(t.id), "amount": 320,
                   "cat": str(cats["餐飲"].id), "merchant": "全家", "groupId": str(g.id)}
    assert one["createdAt"].endswith("Z") and b["notifications"][0]["readAt"].endswith("Z")
    b = api.get("/api/notifications?since=%d" % n2.id, headers=h).json()
    assert b == {"notifications": [], "unread": 1, "maxId": str(n2.id)}               # 紅點不能被清掉
    b = api.get("/api/notifications?since=%d" % n1.id, headers=h).json()
    assert [x["id"] for x in b["notifications"]] == [str(n2.id)]                       # 嚴格大於
    b = api.get("/api/notifications?unreadOnly=true", headers=h).json()
    assert [x["id"] for x in b["notifications"]] == [str(n1.id)]
    fresh = api.get("/api/notifications", headers=login(user("n@x.tw", "新人"))).json()
    assert fresh == {"notifications": [], "unread": 0, "maxId": None}


@pytest.mark.route(*NOTES)
def test_list_notifications_最多_20_則(api):
    me = user("d@x.tw", "爸爸")
    rows = crud.save(Notification, [{"recipient_id": me.id, "type": "ward_transaction"} for _ in range(25)])
    b = api.get("/api/notifications", headers=login(me)).json()
    assert len(b["notifications"]) == 20 and b["notifications"][0]["id"] == str(rows[-1].id)
    assert b["unread"] == 25 and b["maxId"] == str(rows[-1].id)


@pytest.mark.route(*NOTES)
def test_list_notifications_跨過門檻發提醒_一個月只響一次(api):
    me = user("d@x.tw", "爸爸")
    cats = categories()
    g = ledger_of(me, name="旅遊")
    spend(me, g, cats["薪資"], 10000)
    goal(me, 5000)
    low = crud.save(AlertRule, {"user_id": me.id, "percent": 50})
    high = crud.save(AlertRule, {"user_id": me.id, "percent": 100})
    off = crud.save(AlertRule, {"user_id": me.id, "percent": 10, "enabled": False})
    done = crud.save(AlertRule, {"user_id": me.id, "percent": 20, "fired_period": this_month()})
    per_group = crud.save(AlertRule, {"user_id": me.id, "percent": 80, "group_id": g.id})
    h = login(me)
    assert api.get("/api/notifications", headers=h).json()["notifications"] == []
    spend(me, g, cats["餐飲"], 3000)                        # 整體：3000 / (10000−5000) = 60%；旅遊：3000 / 10000 = 30%
    b = api.get("/api/notifications", headers=h).json()
    alerts_ = [x for x in b["notifications"] if x["type"] == "budget_alert"]
    assert [(x["percent"], x["reached"], x["groupName"], x["spent"], x["allowance"]) for x in alerts_] == \
        [(50, 60, "整體", 3000, 5000)]
    assert alerts_[0]["actorId"] is None and alerts_[0]["groupId"] is None
    assert crud.get(AlertRule, low.id).fired_period == this_month()
    assert crud.get(AlertRule, high.id).fired_period is None
    assert crud.get(AlertRule, off.id).fired_period is None and crud.get(AlertRule, done.id).fired_period == this_month()
    assert api.get("/api/notifications?since=%s" % b["maxId"], headers=h).json()["notifications"] == []
    spend(me, g, cats["餐飲"], 6000)                        # 整體 180%、旅遊 90%
    b = api.get("/api/notifications?since=%s" % b["maxId"], headers=h).json()
    got = sorted((x["percent"], x["reached"], x["groupName"]) for x in b["notifications"])
    assert got == [(80, 90, "旅遊"), (100, 180, "整體")]
    assert crud.get(AlertRule, per_group.id).fired_period == this_month()
    assert crud.count(Notification) == 3


@pytest.mark.route(*READ)
def test_read_notification(api):
    me, other = user("d@x.tw", "爸爸"), user("o@x.tw", "別人")
    n = _note(me)
    theirs = _note(other)
    h = login(me)
    r = api.patch("/api/notifications/%d" % n.id, headers=h, json={"read": True})
    assert r.status_code == 200 and r.json()["id"] == str(n.id) and r.json()["readAt"].endswith("Z")
    first = r.json()["readAt"]
    assert api.patch("/api/notifications/%d" % n.id, headers=h, json={}).json()["readAt"] == first
    r = api.patch("/api/notifications/%d" % n.id, headers=h, json={"read": False})
    assert r.json() == {"id": str(n.id), "readAt": None} and crud.get(Notification, n.id).read_at is None
    assert api.patch("/api/notifications/%d" % theirs.id, headers=h, json={"read": True}).status_code == 403
    assert api.patch("/api/notifications/99999", headers=h, json={"read": True}).status_code == 404


@pytest.mark.route(*READALL)
def test_read_notifications_只標到_readUntil(api):
    me, other = user("d@x.tw", "爸爸"), user("o@x.tw", "別人")
    a, b, c = _note(me), _note(me), _note(me)
    _note(other)
    h = login(me)
    assert api.patch("/api/notifications", headers=h, json={}).status_code == 400
    r = api.patch("/api/notifications", headers=h, json={"readUntil": str(b.id)})
    assert r.status_code == 200 and r.json() == {"updated": 2, "unread": 1}
    assert crud.get(Notification, c.id).read_at is None and crud.get(Notification, a.id).read_at is not None
    assert crud.count(Notification, {"read_at__isnull": True}) == 2          # 別人的不受影響
    r = api.patch("/api/notifications", headers=h, json={"readUntil": str(c.id)})
    assert r.json() == {"updated": 1, "unread": 0}
