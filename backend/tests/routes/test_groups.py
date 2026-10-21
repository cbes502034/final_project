"""分類與帳本（記帳）。怎麼跑、兩種對象的差別：看 conftest.py 的檔頭。"""

import pytest

from app.models import AuditLog, Category, Group, GroupMember, Transaction
from app.toolkit import crud
from tests.routes.conftest import categories, family_of, goal, ledger_of, login, now, spend, user


# ===========================================================================
# GET /api/categories
# ===========================================================================
CATS = ("GET", "/api/categories")


@pytest.mark.route(*CATS)
def test_list_categories_系統的加我們家的(api):
    me, other = user("d@x.tw", "爸爸"), user("o@x.tw", "別家")
    fam = family_of((me, "parent"))
    other_fam = family_of((other, "parent"), name="林家")
    cats = categories(fam)
    crud.save(Category, {"name": "別家的", "kind": "expense", "color": "cat-other", "family_id": other_fam.id})
    r = api.get("/api/categories", headers=login(me))
    assert r.status_code == 200, r.text
    rows = r.json()["categories"]
    assert [c["name"] for c in rows] == ["餐飲", "其他", "薪資", "其他收入", "寵物"]
    assert rows[0] == {"id": str(cats["餐飲"].id), "name": "餐飲", "kind": "expense", "color": "cat-food",
                       "icon": "食", "custom": False}
    assert rows[3]["icon"] == "收"
    assert rows[-1] == {"id": str(cats["寵物"].id), "name": "寵物", "kind": "expense", "color": "cat-other",
                        "icon": "寵", "custom": True, "familyId": str(fam.id)}
    lonely = user("l@x.tw", "沒有家")
    assert len(api.get("/api/categories", headers=login(lonely)).json()["categories"]) == 4


# ===========================================================================
# POST /api/categories
# ===========================================================================
NEWCAT = ("POST", "/api/categories")


@pytest.mark.route(*NEWCAT)
def test_create_category_家長新增_重名與格式(api):
    dad, kid = user("d@x.tw", "爸爸"), user("k@x.tw", "小華")
    fam = family_of((dad, "parent"), (kid, "child"))
    categories()
    h = login(dad)
    r = api.post("/api/categories", headers=h, json={"name": " 寵 物 ", "kind": "expense"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body == {"id": body["id"], "name": "寵 物", "kind": "expense", "color": "cat-other", "icon": "寵",
                    "custom": True, "familyId": str(fam.id)}
    assert crud.get(Category, int(body["id"])).family_id == fam.id
    assert api.post("/api/categories", headers=h, json={"name": "寵 物", "kind": "expense"}).status_code == 409
    assert api.post("/api/categories", headers=h, json={"name": "餐飲", "kind": "expense"}).status_code == 409
    assert api.post("/api/categories", headers=h, json={"name": "餐飲", "kind": "income"}).status_code == 201
    assert api.post("/api/categories", headers=h, json={"name": "   ", "kind": "expense"}).status_code == 422
    assert api.post("/api/categories", headers=h, json={"name": "x", "kind": "gift"}).status_code == 422
    assert api.post("/api/categories", headers=login(kid), json={"name": "零食", "kind": "expense"}).status_code == 403


# ===========================================================================
# GET /api/groups
# ===========================================================================
LIST = ("GET", "/api/groups")


@pytest.mark.route(*LIST)
def test_list_groups_只有我加入的_帶上成員筆數目標(api):
    dad, mom, stranger = user("d@x.tw", "爸爸"), user("m@x.tw", "媽媽"), user("s@x.tw", "路人")
    cats = categories()
    home = ledger_of(dad, mom, color="book-teal", note="日常")
    trip = ledger_of(mom, dad, name="旅遊", kind="temp", ends_on=now().date().replace(year=2000))
    shelved = ledger_of(dad, name="舊的", archived_at=now())
    ledger_of(dad, name="移除的", kind="temp", settled_at=now(), removed_at=now())
    ledger_of(stranger, name="別人的")
    spend(dad, home, cats["餐飲"], 1)
    spend(mom, home, cats["餐飲"], 2)
    goal(dad, 3000, group=home)
    goal(dad, 5000, group=home)
    crud.save(GroupMember, {"notify": True}, where={"group_id": trip.id, "user_id": dad.id})
    r = api.get("/api/groups", headers=login(dad))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["me"] == str(dad.id)
    assert [g["name"] for g in body["groups"]] == ["家用", "旅遊"]
    h, t = body["groups"]
    assert h["members"] == [str(dad.id), str(mom.id)] and h["memberNames"] == ["爸爸", "媽媽"]
    assert (h["count"], h["goal"], h["canEdit"], h["notify"]) == (2, 5000, True, False)
    assert (h["icon"], h["color"], h["note"], h["kind"], h["archived"], h["settled"]) == \
        ("用", "book-teal", "日常", "standing", False, False)
    assert (t["canEdit"], t["notify"], t["overdue"], t["kind"], t["goal"]) == (False, True, True, "temp", 0)
    names = [g["name"] for g in api.get("/api/groups?includeArchived=true", headers=login(dad)).json()["groups"]]
    assert names == ["家用", "旅遊", "舊的"]
    assert next(g for g in api.get("/api/groups?includeArchived=true", headers=login(dad)).json()["groups"]
                if g["id"] == str(shelved.id))["archived"] is True
    newbie = user("n@x.tw", "新人")
    assert api.get("/api/groups", headers=login(newbie)).json() == {"me": str(newbie.id), "groups": []}


# ===========================================================================
# POST /api/groups
# ===========================================================================
NEW = ("POST", "/api/groups")


@pytest.mark.route(*NEW)
def test_create_group_建立者自動加入(api):
    me = user("d@x.tw", "爸爸")
    r = api.post("/api/groups", headers=login(me), json={"name": " 旅遊 基金 ", "kind": "temp",
                                                          "endsOn": "2026-10-05", "color": "book-violet"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert (body["name"], body["kind"], body["endsOn"], body["color"], body["members"], body["canEdit"]) == \
        ("旅遊 基金", "temp", "2026-10-05", "book-violet", [str(me.id)], True)
    assert crud.exists(GroupMember, {"group_id": int(body["id"]), "user_id": me.id})
    r = api.post("/api/groups", headers=login(me), json={"name": "家用"})
    assert r.status_code == 201 and r.json()["color"] == "book-indigo" and r.json()["endsOn"] is None


@pytest.mark.route(*NEW)
def test_create_group_重名只比自己家_格式檢查(api):
    dad, mom, stranger = user("d@x.tw", "爸爸"), user("m@x.tw", "媽媽"), user("s@x.tw", "路人")
    family_of((dad, "parent"), (mom, "parent"))
    ledger_of(mom, name="家用", archived_at=now())
    ledger_of(stranger, name="旅遊")
    h = login(dad)
    r = api.post("/api/groups", headers=h, json={"name": "家用"})
    assert r.status_code == 409 and "家用" in r.json()["detail"]
    assert api.post("/api/groups", headers=h, json={"name": "旅遊"}).status_code == 201
    assert api.post("/api/groups", headers=h, json={"name": "a", "kind": "temp"}).status_code == 400
    assert api.post("/api/groups", headers=h, json={"name": "b", "kind": "temp", "endsOn": "10/5"}).status_code == 422
    assert api.post("/api/groups", headers=h, json={"name": "c", "color": "red"}).status_code == 422
    assert api.post("/api/groups", headers=h, json={"name": "   "}).status_code == 422
    assert api.post("/api/groups", headers=h, json={"name": "d", "kind": "weird"}).status_code == 422
    assert crud.count(Group) == 3


# ===========================================================================
# PATCH /api/groups/{gid}
# ===========================================================================
PATCH = ("PATCH", "/api/groups/{gid}")


@pytest.mark.route(*PATCH)
def test_update_group_改名換色復原(api):
    me, mom = user("d@x.tw", "爸爸"), user("m@x.tw", "媽媽")
    family_of((me, "parent"), (mom, "parent"))
    g = ledger_of(me, mom, name="家用", archived_at=now())
    ledger_of(mom, name="旅遊")
    h = login(me)
    url = "/api/groups/%d" % g.id
    r = api.patch(url, headers=h, json={"name": "家用開銷", "color": "book-moss", "note": " 日常 "})
    assert r.status_code == 200, r.text
    assert (r.json()["name"], r.json()["color"], r.json()["note"], r.json()["archived"]) == \
        ("家用開銷", "book-moss", "日常", True)
    r = api.patch(url, headers=h, json={"archived": False})
    assert r.status_code == 200 and r.json()["archived"] is False
    assert crud.get(Group, g.id).archived_at is None
    assert api.patch(url, headers=h, json={"name": "家用開銷"}).status_code == 200      # 跟自己同名不算重複
    assert api.patch(url, headers=h, json={"name": "旅遊"}).status_code == 409
    assert api.patch(url, headers=h, json={"color": "red"}).status_code == 422
    assert api.patch(url, headers=h, json={"archived": True}).status_code == 422
    assert api.patch(url, headers=h, json={"name": "   "}).status_code == 422
    assert api.patch(url, headers=h, json={"owner": "3"}).status_code == 422
    assert api.patch(url, headers=h, json={}).status_code == 400
    assert api.patch(url, headers=login(mom), json={"name": "x"}).status_code == 403
    assert api.patch("/api/groups/99999", headers=h, json={"name": "x"}).status_code == 404


# ===========================================================================
# DELETE /api/groups/{gid}
# ===========================================================================
DEL = ("DELETE", "/api/groups/{gid}")


@pytest.mark.route(*DEL)
def test_archive_or_remove_group(api):
    me, mom = user("d@x.tw", "爸爸"), user("m@x.tw", "媽媽")
    cats = categories()
    g = ledger_of(me, mom)
    trip = ledger_of(me, name="旅遊", kind="temp")
    spend(me, trip, cats["餐飲"], 10)
    h = login(me)
    r = api.delete("/api/groups/%d" % g.id, headers=h)
    assert r.status_code == 200 and r.json() == {"id": str(g.id), "archived": True}
    assert crud.get(Group, g.id).archived_at is not None and crud.get(Group, g.id).removed_at is None
    assert api.delete("/api/groups/%d" % g.id, headers=login(mom)).status_code == 403
    r = api.delete("/api/groups/%d?permanent=true" % trip.id, headers=h)
    assert r.status_code == 409 and "結算" in r.json()["detail"]
    crud.save(Group, {"id": trip.id, "settled_at": now()})
    r = api.delete("/api/groups/%d?permanent=true" % trip.id, headers=h)
    assert r.status_code == 200 and r.json() == {"id": str(trip.id), "removed": True}
    assert crud.get(Group, trip.id).removed_at is not None
    assert crud.count(Transaction) == 1                                           # 紀錄一筆都不刪
    assert crud.get(AuditLog, where={"action": "remove_group"}).target_id == trip.id
    assert api.delete("/api/groups/%d?permanent=true" % trip.id, headers=h).status_code == 404


# ===========================================================================
# POST /api/groups/{gid}/members
# ===========================================================================
ADD = ("POST", "/api/groups/{gid}/members")


@pytest.mark.route(*ADD)
def test_add_group_member_只能加家人(api):
    dad, kid, stranger = user("d@x.tw", "爸爸"), user("k@x.tw", "小華"), user("s@x.tw", "路人")
    family_of((dad, "parent"), (kid, "child"))
    family_of((stranger, "parent"), name="林家")
    g = ledger_of(dad)
    h = login(dad)
    url = "/api/groups/%d/members" % g.id
    r = api.post(url, headers=h, json={"userId": str(kid.id)})
    assert r.status_code == 201 and r.json() == {"group": str(g.id), "user": str(kid.id)}
    assert crud.get(GroupMember, (g.id, kid.id)).notify is False
    assert api.post(url, headers=h, json={"userId": str(kid.id)}).status_code == 409
    assert api.post(url, headers=h, json={"userId": str(stranger.id)}).status_code == 404
    assert api.post(url, headers=h, json={"userId": "abc"}).status_code == 404
    assert api.post(url, headers=login(kid), json={"userId": str(dad.id)}).status_code == 403
    lonely = user("l@x.tw", "沒有家")
    mine = ledger_of(lonely, name="自己的")
    r = api.post("/api/groups/%d/members" % mine.id, headers=login(lonely), json={"userId": str(dad.id)})
    assert r.status_code == 404


# ===========================================================================
# DELETE /api/groups/{gid}/members/{user_id}
# ===========================================================================
KICK = ("DELETE", "/api/groups/{gid}/members/{user_id}")


@pytest.mark.route(*KICK)
def test_remove_group_member(api):
    dad, kid = user("d@x.tw", "爸爸"), user("k@x.tw", "小華")
    cats = categories()
    g = ledger_of(dad, kid)
    spend(kid, g, cats["餐飲"], 10)
    h = login(dad)
    r = api.delete("/api/groups/%d/members/%d" % (g.id, kid.id), headers=h)
    assert r.status_code == 200 and r.json() == {"group": str(g.id), "user": str(kid.id), "removed": True}
    assert not crud.exists(GroupMember, {"group_id": g.id, "user_id": kid.id})
    assert crud.count(Transaction) == 1
    assert api.delete("/api/groups/%d/members/%d" % (g.id, kid.id), headers=h).status_code == 404
    assert api.delete("/api/groups/%d/members/%d" % (g.id, dad.id), headers=h).status_code == 400


# ===========================================================================
# POST /api/groups/{gid}/settle
# ===========================================================================
SETTLE = ("POST", "/api/groups/{gid}/settle")


@pytest.mark.route(*SETTLE)
def test_settle_group_copies_the_callers_rows_and_keeps_shared_history(api):
    me, mom, stranger = user("d@x.tw", "爸爸"), user("m@x.tw", "媽媽"), user("s@x.tw", "路人")
    cats = categories()
    trip = ledger_of(me, mom, name="旅遊", kind="temp")
    own = spend(me, trip, cats["餐飲"], 10)
    hers = spend(mom, trip, cats["餐飲"], 20)
    original = (own.occurred_on, own.amount, own.user_id)
    assert api.post(f"/api/groups/{trip.id}/settle", headers=login(stranger)).status_code == 403

    # A non-owner can merge independently, without closing the shared book.
    r = api.post(f"/api/groups/{trip.id}/settle", headers=login(mom))
    assert r.status_code == 200, r.text
    result = r.json()
    assert result["copied"] == 1 and result["closed"] is False and result["settledAt"] is None
    personal = crud.get(Group, int(result["personalGroupId"]))
    assert personal.personal_owner_id == mom.id
    assert crud.get(Transaction, hers.id).group_id == trip.id
    assert crud.get(Transaction, hers.id).is_snapshot is True
    copied = crud.get(Transaction, where={"copied_from_id": hers.id})
    assert copied and copied.id != hers.id and copied.group_id == personal.id
    assert copied.user_id == mom.id and copied.amount == hers.amount
    assert copied.is_snapshot is False
    assert crud.get(Transaction, own.id).group_id == trip.id
    assert crud.count(Transaction) == 3
    assert not crud.exists(GroupMember, {"group_id": trip.id, "user_id": mom.id})
    assert crud.exists(GroupMember, {"group_id": trip.id, "user_id": me.id})
    assert crud.get(Group, trip.id).settled_at is None
    assert api.post(f"/api/groups/{trip.id}/settle", headers=login(mom)).status_code == 403
    assert [g["id"] for g in api.get("/api/groups", headers=login(mom)).json()["groups"]] == [str(personal.id)]
    rows = api.get(f"/api/transactions?groupId={personal.id}", headers=login(mom)).json()["transactions"]
    assert [t["id"] for t in rows] == [str(copied.id)]
    assert all(t["user"] == str(mom.id) for t in rows)

    shared_rows = api.get(f"/api/transactions?groupId={trip.id}", headers=login(me)).json()["transactions"]
    assert {t["id"] for t in shared_rows} == {str(own.id), str(hers.id)}
    hers_history = next(t for t in shared_rows if t["id"] == str(hers.id))
    assert hers_history["amount"] == 20 and hers_history["snapshot"] is True
    filtered = api.get(f"/api/transactions?groupId={trip.id}&userId={mom.id}", headers=login(me))
    assert filtered.status_code == 200 and filtered.json()["total"] == 1
    assert api.get("/api/summary?scope=me", headers=login(mom)).json()["expense"] == 20
    assert api.get("/api/transactions", headers=login(mom)).json()["total"] == 1

    # The member who stayed can still add entries, then close the book last.
    added = api.post("/api/transactions", headers=login(me), json={
        "date": now().date().isoformat(), "amount": 30, "kind": "expense", "cat": str(cats["餐飲"].id),
        "groupId": str(trip.id), "merchant": "午餐"})
    assert added.status_code == 201, added.text
    last = api.post(f"/api/groups/{trip.id}/settle", headers=login(me))
    assert last.status_code == 200, last.text
    assert last.json()["closed"] and last.json()["copied"] == 2
    closed = crud.get(Group, trip.id)
    assert closed.settled_at and closed.removed_at
    assert not crud.exists(GroupMember, {"group_id": trip.id})
    assert crud.count(Transaction) == 6
    moved = crud.get(Transaction, own.id)
    assert (moved.occurred_on, moved.amount, moved.user_id) == original
    assert str(trip.id) not in [g["id"] for g in api.get("/api/groups", headers=login(me)).json()["groups"]]
    assert api.post(f"/api/groups/{closed.id}/settle", headers=login(me)).status_code == 404
    assert api.post(f"/api/groups/{personal.id}/settle", headers=login(mom)).status_code == 400


@pytest.mark.route(*SETTLE)
def test_owner_can_merge_a_standing_book_and_transfer_management(api):
    owner, member = user("o@x.tw", "開帳者"), user("m@x.tw", "成員")
    g = ledger_of(owner, member)
    cats = categories()
    tx = spend(owner, g, cats["餐飲"], 15)
    r = api.post(f"/api/groups/{g.id}/settle", headers=login(owner))
    assert r.status_code == 200, r.text
    assert r.json()["closed"] is False
    assert crud.get(Transaction, tx.id).group_id == g.id
    assert crud.get(Transaction, where={"copied_from_id": tx.id}).group_id == int(r.json()["personalGroupId"])
    assert crud.get(Group, g.id).created_by == member.id
    assert api.patch(f"/api/groups/{g.id}", headers=login(member), json={"name": "繼續使用"}).status_code == 200
    assert api.patch(f"/api/groups/{g.id}", headers=login(owner), json={"name": "不應該能改"}).status_code == 403
    # Zero-entry members can leave too; merging does not create duplicate transactions.
    last = api.post(f"/api/groups/{g.id}/settle", headers=login(member))
    assert last.status_code == 200 and last.json()["copied"] == 0 and last.json()["closed"]
    assert crud.count(Transaction) == 2


@pytest.mark.route(*SETTLE)
def test_merge_reuses_personal_book_after_rename_and_protects_it(api):
    me, other = user("o@x.tw", "本人"), user("m@x.tw", "家人")
    family_of((me, "parent"), (other, "parent"))
    personal = ledger_of(me, name="改名的大帳本", personal_owner_id=me.id)
    first, second = ledger_of(me, name="第一本"), ledger_of(me, name="第二本")
    for source in (first, second):
        r = api.post(f"/api/groups/{source.id}/settle", headers=login(me))
        assert r.status_code == 200 and r.json()["personalGroupId"] == str(personal.id)
    assert crud.count(Group, {"personal_owner_id": me.id}) == 1
    assert api.delete(f"/api/groups/{personal.id}", headers=login(me)).status_code == 400
    assert api.post(f"/api/groups/{personal.id}/members", headers=login(me), json={"userId": str(other.id)}).status_code == 400
    assert api.get("/api/groups", headers=login(me)).json()["groups"][0]["personal"] is True


@pytest.mark.route(*SETTLE)
def test_copy_preserves_history_without_doubling_family_spending_and_cannot_repeat(api):
    from app.models import Allowance, Budget, NlpParse
    from tests.routes.conftest import guard

    parent, child = user("p@x.tw", "家長"), user("c@x.tw", "子女")
    family_of((parent, "parent"), (child, "child"))
    guard(parent, child)
    shared = ledger_of(parent, child)
    cat = categories()["餐飲"]
    original = spend(child, shared, cat, 100)
    crud.save(Transaction, {"id": original.id, "source": "nlp"})
    crud.save(NlpParse, {"transaction_id": original.id, "user_id": child.id,
                         "raw_text": "午餐100", "confidence": 0.9, "cat_confidence": 0.8})
    crud.save(Allowance, {"payer_id": parent.id, "ward_id": child.id, "amount": 3000})
    crud.save(Budget, {"user_id": child.id, "category_id": cat.id, "limit_amount": 200,
                       "period_type": "month", "created_by": child.id})
    h = login(child)
    r = api.post(f"/api/groups/{shared.id}/settle", headers=h)
    assert r.status_code == 200 and r.json()["copied"] == 1
    personal_id = r.json()["personalGroupId"]
    copied = crud.get(Transaction, where={"copied_from_id": original.id})
    assert api.get("/api/summary?scope=family", headers=login(parent)).json()["expense"] == 100
    assert api.get("/api/budgets", headers=h).json()["budgets"][0]["used"] == 100
    assert api.get("/api/allowances", headers=login(parent)).json()["allowances"][0]["spent"] == 100
    view = api.get(f"/api/transactions?groupId={personal_id}", headers=h).json()["transactions"][0]
    assert view["raw"] == "午餐100" and view["parsed"]["conf"] == 0.9

    # Rejoining cannot generate another copy of the same historical entry.
    crud.save(GroupMember, {"group_id": shared.id, "user_id": child.id})
    again = api.post(f"/api/groups/{shared.id}/settle", headers=h)
    assert again.status_code == 200 and again.json()["copied"] == 0
    assert crud.count(Transaction) == 2
    assert api.patch(f"/api/transactions/{original.id}", headers=h, json={"amount": 999}).status_code == 409
    assert api.delete(f"/api/transactions/{original.id}", headers=h).status_code == 409
    assert api.delete(f"/api/transactions?ids={original.id},{copied.id}", headers=h).status_code == 409
    assert crud.count(Transaction) == 2

    # Personal corrections affect the copy while the shared book keeps the pre-settlement figures.
    edited = api.patch(f"/api/transactions/{copied.id}", headers=h, json={"amount": 120})
    assert edited.status_code == 200, edited.text
    assert crud.get(Transaction, original.id).amount == 100
    assert crud.get(Transaction, copied.id).amount == 120
    assert api.get("/api/summary?scope=family", headers=login(parent)).json()["expense"] == 120
    assert api.delete(f"/api/transactions/{copied.id}", headers=h).status_code == 200
    assert crud.get(Transaction, original.id).amount == 100
    history = api.get(f"/api/transactions?groupId={shared.id}", headers=login(parent)).json()
    assert history["total"] == 1 and history["transactions"][0]["amount"] == 100
    assert api.get("/api/summary?scope=family", headers=login(parent)).json()["expense"] == 0


# ===========================================================================
# PATCH /api/groups/{gid}/notify
# ===========================================================================
NOTIFY = ("PATCH", "/api/groups/{gid}/notify")


@pytest.mark.route(*NOTIFY)
def test_set_group_notify_只改我自己那一列(api):
    dad, mom, stranger = user("d@x.tw", "爸爸"), user("m@x.tw", "媽媽"), user("s@x.tw", "路人")
    g = ledger_of(dad, mom)
    r = api.patch("/api/groups/%d/notify" % g.id, headers=login(mom), json={"notify": True})
    assert r.status_code == 200 and r.json() == {"group": str(g.id), "notify": True}
    assert crud.get(GroupMember, (g.id, mom.id)).notify is True
    assert crud.get(GroupMember, (g.id, dad.id)).notify is False
    assert api.patch("/api/groups/%d/notify" % g.id, headers=login(stranger), json={"notify": True}).status_code == 403
    assert api.patch("/api/groups/%d/notify" % g.id, headers=login(mom), json={"notify": "maybe"}).status_code == 422


# ===========================================================================
# DELETE /api/categories/{cid}：自訂分類可以刪，紀錄改到「其他」
# ===========================================================================
DELCAT = ("DELETE", "/api/categories/{cid}")


@pytest.mark.route(*DELCAT)
def test_delete_category_紀錄改到其他_預算拿掉_系統分類不能刪(api):
    from app.models import Budget
    dad, kid = user("d@x.tw", "爸爸"), user("k@x.tw", "小華")
    fam = family_of((dad, "parent"), (kid, "child"))
    cats = categories(fam)                                  # 「寵物」是我們家的自訂分類
    g = ledger_of(dad)
    t = spend(dad, g, cats["寵物"], 300)
    crud.save(Budget, {"user_id": dad.id, "category_id": cats["寵物"].id, "period_type": "month", "limit_amount": 1000,
                       "created_by": dad.id})
    assert api.delete("/api/categories/%d" % cats["寵物"].id, headers=login(kid)).status_code == 403   # 子女
    r = api.delete("/api/categories/%d" % cats["餐飲"].id, headers=login(dad))
    assert r.status_code == 403 and "系統分類" in r.json()["detail"]
    r = api.delete("/api/categories/%d" % cats["寵物"].id, headers=login(dad))
    assert r.status_code == 200 and r.json() == {"id": str(cats["寵物"].id), "deleted": True, "moved": 1}
    assert crud.get(Transaction, t.id).category_id == cats["其他"].id                    # 紀錄還在，改到「其他」
    assert not crud.exists(Category, {"id": cats["寵物"].id})
    assert not crud.exists(Budget, {"category_id": cats["寵物"].id})
    assert api.delete("/api/categories/%d" % cats["寵物"].id, headers=login(dad)).status_code == 404
    other = user("o@x.tw", "別家")
    fam2 = family_of((other, "parent"), name="別家")
    theirs = crud.save(Category, {"name": "別家的", "kind": "expense", "color": "cat-other", "family_id": fam2.id})
    assert api.delete("/api/categories/%d" % theirs.id, headers=login(dad)).status_code == 404
