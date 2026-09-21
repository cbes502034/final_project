"""收支明細：查、記、改、刪（成員2）。怎麼跑、兩種對象的差別：看 conftest.py 的檔頭。"""

import pytest

from app.models import Category, GroupMember, NlpParse, Notification, Transaction
from app.toolkit import crud
from tests.routes.conftest import (
    categories, family_of, guard, ledger_of, login, now, spend, today, user,
)


# ===========================================================================
# GET /api/transactions
# ===========================================================================
LIST = ("GET", "/api/transactions")


@pytest.mark.route(*LIST)
def test_list_transactions_看得到的是監管與同帳本的聯集(api):
    dad, kid, aunt, stranger = (user(e, n) for e, n in (
        ("d@x.tw", "爸爸"), ("k@x.tw", "小華"), ("a@x.tw", "阿姨"), ("s@x.tw", "路人")))
    fam = family_of((dad, "parent"), (kid, "child"))
    guard(dad, kid)
    cats = categories(fam)
    home = ledger_of(dad, aunt)
    kids_own = ledger_of(kid, name="小華的帳")
    theirs = ledger_of(stranger, name="別人的帳")
    mine = spend(dad, home, cats["餐飲"], 100)
    by_aunt = spend(aunt, home, cats["餐飲"], 50)
    by_kid = spend(kid, kids_own, cats["餐飲"], 30, merchant="全家")
    spend(stranger, theirs, cats["餐飲"], 999)
    r = api.get("/api/transactions", headers=login(dad))
    assert r.status_code == 200, r.text
    body = r.json()
    assert {t["id"] for t in body["transactions"]} == {str(mine.id), str(by_aunt.id), str(by_kid.id)}
    assert body["total"] == 3
    one = next(t for t in body["transactions"] if t["id"] == str(by_kid.id))
    assert one == {"id": str(by_kid.id), "user": str(kid.id), "date": today(), "amount": 30, "group": str(kids_own.id),
                   "kind": "expense", "cat": str(cats["餐飲"].id), "source": "manual", "merchant": "全家",
                   "note": "", "raw": "", "parsed": {"conf": 1, "catConf": 1}}


@pytest.mark.route(*LIST)
def test_list_transactions_篩選與權限(api):
    dad, aunt, stranger = user("d@x.tw", "爸爸"), user("a@x.tw", "阿姨"), user("s@x.tw", "路人")
    cats = categories()
    home = ledger_of(dad, aunt)
    other = ledger_of(stranger, name="別人的帳")
    spend(dad, home, cats["餐飲"], 100, day="2026-09-01", merchant="全聯")
    spend(dad, home, cats["薪資"], 5000, day="2026-09-05", note="九月薪水")
    spend(aunt, home, cats["餐飲"], 70, day="2026-09-03")
    h = login(dad)
    got = lambda q: [t["amount"] for t in api.get("/api/transactions" + q, headers=h).json()["transactions"]]  # noqa: E731
    assert got("?from=2026-09-02&to=2026-09-05") == [5000, 70]
    assert got("?kind=income") == [5000]
    assert got("?q=%E5%85%A8%E8%81%AF") == [100]                   # q=全聯
    assert got("?userId=%d" % aunt.id) == [70]                      # 同帳本的人查得到
    assert got("?groupId=all&kind=all") == [5000, 70, 100]
    assert api.get("/api/transactions?userId=%d" % stranger.id, headers=h).status_code == 403
    assert api.get("/api/transactions?groupId=%d" % other.id, headers=h).status_code == 403
    r = api.get("/api/transactions?user=3", headers=h)
    assert r.status_code == 422 and "user" in r.json()["detail"]
    assert api.get("/api/transactions?from=9/1", headers=h).status_code == 422
    assert api.get("/api/transactions?kind=gift", headers=h).status_code == 422


@pytest.mark.route(*LIST)
def test_list_transactions_段落記帳的帶原句與信心度(api):
    me = user("d@x.tw", "爸爸")
    cats = categories()
    g = ledger_of(me)
    t = spend(me, g, cats["餐飲"], 55, source="nlp")
    crud.save(NlpParse, {"transaction_id": t.id, "user_id": me.id, "raw_text": "早餐55", "confidence": 0.9,
                         "cat_confidence": 0.7})
    row = api.get("/api/transactions?source=nlp", headers=login(me)).json()["transactions"][0]
    assert row["raw"] == "早餐55" and row["parsed"] == {"conf": 0.9, "catConf": 0.7}


# ===========================================================================
# POST /api/transactions
# ===========================================================================
TX = ("POST", "/api/transactions")


@pytest.mark.route(*TX)
def test_create_transaction_記一筆_回傳前端要的形狀(api):
    me = user("dad@x.tw", "王大明")
    fam = family_of((me, "parent"))
    g = ledger_of(me)
    cat = categories(fam)["餐飲"]
    r = api.post("/api/transactions", headers=login(me), json={
        "date": "2026-09-17", "amount": 120.5, "kind": "expense", "cat": str(cat.id), "merchant": " 全家 ", "note": ""})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["id"] and isinstance(body["id"], str)
    assert {k: body[k] for k in ("user", "date", "amount", "group", "kind", "cat", "source", "merchant", "note")} == {
        "user": str(me.id), "date": "2026-09-17", "amount": 120.5, "group": str(g.id), "kind": "expense",
        "cat": str(cat.id), "source": "manual", "merchant": "全家", "note": ""}
    row = crud.get(Transaction, int(body["id"]))
    assert row.family_id == fam.id and row.source == "manual" and str(row.amount) == "120.50"


@pytest.mark.route(*TX)
def test_create_transaction_沒帶帳本_記進第一本還能記的(api):
    me = user("dad@x.tw", "王大明")
    ledger_of(me, name="已結算", kind="temp", settled_at=now())
    ledger_of(me, name="已封存", archived_at=now())
    ok = ledger_of(me, name="家用")
    cat = categories()["餐飲"]
    r = api.post("/api/transactions", headers=login(me), json={"date": "2026-09-17", "amount": 1, "kind": "expense", "cat": str(cat.id)})
    assert r.status_code == 201, r.text
    assert r.json()["group"] == str(ok.id)


@pytest.mark.route(*TX)
def test_create_transaction_帳本不對的三種情況(api):
    me = user("dad@x.tw", "王大明")
    other = user("x@x.tw", "別人")
    cat = categories()["餐飲"]
    base = {"date": "2026-09-17", "amount": 1, "kind": "expense", "cat": str(cat.id)}

    r = api.post("/api/transactions", headers=login(me), json=base)                  # 一本帳都沒有
    assert r.status_code == 409 and "帳本" in r.json()["detail"]
    theirs = ledger_of(other)                                                        # 別人的帳本：不透露它存在
    r = api.post("/api/transactions", headers=login(me), json={**base, "groupId": str(theirs.id)})
    assert r.status_code == 404
    done = ledger_of(me, kind="temp", settled_at=now())                              # 結算過的
    r = api.post("/api/transactions", headers=login(me), json={**base, "groupId": str(done.id)})
    assert r.status_code == 409 and "結算" in r.json()["detail"]
    assert crud.count(Transaction) == 0


@pytest.mark.route(*TX)
def test_create_transaction_分類要存在_要是自己家的_收支要對得上(api):
    me, stranger = user("dad@x.tw", "王大明"), user("s@x.tw", "別家")
    fam = family_of((me, "parent"))
    other_fam = family_of((stranger, "parent"))
    ledger_of(me)
    cats = categories(fam)
    theirs = crud.save(Category, {"name": "別家的", "kind": "expense", "color": "cat-other", "family_id": other_fam.id})
    base = {"date": "2026-09-17", "amount": 1, "kind": "expense"}
    for cat, code in ((cats["寵物"].id, 201), (cats["薪資"].id, 400), (theirs.id, 400), ("abc", 400), (99999, 400)):
        r = api.post("/api/transactions", headers=login(me), json={**base, "cat": str(cat)})
        assert r.status_code == code, (cat, r.text)
        if code == 400:
            assert r.json()["detail"]


@pytest.mark.route(*TX)
def test_create_transaction_格式不對回_422(api):
    me = user("dad@x.tw", "王大明")
    ledger_of(me)
    cat = categories()["餐飲"]
    for bad in ({"date": "9/17"}, {"amount": 0}, {"amount": -5}, {"kind": "transfer"}):
        body = {"date": "2026-09-17", "amount": 1, "kind": "expense", "cat": str(cat.id), **bad}
        assert api.post("/api/transactions", headers=login(me), json=body).status_code == 422, bad


@pytest.mark.route(*TX)
def test_create_transaction_守衛_沒登入_平台管理員(api):
    admin = user("admin@x.tw", "管理員", is_platform_admin=True)
    body = {"date": "2026-09-17", "amount": 1, "kind": "expense", "cat": "1"}
    assert api.post("/api/transactions", json=body).status_code == 401
    assert api.post("/api/transactions", headers=login(admin), json=body).status_code == 403


@pytest.mark.route(*TX)
def test_create_transaction_通知監管我的人與開了通知的帳本成員_每人一則(api):
    kid, mom, dad, aunt = (user(e, n) for e, n in (("k@x.tw", "小華"), ("m@x.tw", "媽媽"), ("d@x.tw", "爸爸"), ("a@x.tw", "阿姨")))
    fam = family_of((dad, "parent"), (mom, "parent"), (kid, "child"))
    guard(mom, kid)
    g = ledger_of(kid, mom, dad, aunt)
    # 媽媽：監管＋開了通知 → 只收一則（監管優先）；爸爸：沒監管、沒開 → 不收；阿姨：開了通知 → 收
    crud.save(GroupMember, {"notify": True}, where={"group_id": g.id, "user_id__in": [mom.id, aunt.id]})
    cat = categories(fam)["餐飲"]
    r = api.post("/api/transactions", headers=login(kid), json={"date": "2026-09-17", "amount": 80, "kind": "expense", "cat": str(cat.id)})
    assert r.status_code == 201, r.text
    got = {n.recipient_id: n.type for n in crud.find(Notification)}
    assert got == {mom.id: "ward_transaction", aunt.id: "group_transaction"}
    assert all(n.transaction_id == int(r.json()["id"]) and n.actor_id == kid.id for n in crud.find(Notification))


# ===========================================================================
# PATCH /api/transactions/{tx_id}
# ===========================================================================
PATCH = ("PATCH", "/api/transactions/{tx_id}")


@pytest.mark.route(*PATCH)
def test_update_transaction_只改送來的欄位(api):
    me = user("d@x.tw", "爸爸")
    cats = categories()
    g = ledger_of(me)
    t = spend(me, g, cats["餐飲"], 100, merchant="全家", note="午餐")
    r = api.patch("/api/transactions/%d" % t.id, headers=login(me), json={"amount": 180, "note": " 午餐  飲料 "})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["amount"] == 180 and body["note"] == "午餐 飲料" and body["merchant"] == "全家"
    assert body["updatedAt"] and body["id"] == str(t.id) and body["cat"] == str(cats["餐飲"].id)
    assert str(crud.get(Transaction, t.id).amount) == "180.00"


@pytest.mark.route(*PATCH)
def test_update_transaction_分類與收支(api):
    me = user("d@x.tw", "爸爸")
    cats = categories()
    g = ledger_of(me)
    t = spend(me, g, cats["餐飲"], 100)
    h = login(me)
    r = api.patch("/api/transactions/%d" % t.id, headers=h, json={"cat": str(cats["薪資"].id)})
    assert r.status_code == 400 and "收入" in r.json()["detail"]
    r = api.patch("/api/transactions/%d" % t.id, headers=h, json={"kind": "income"})
    assert r.status_code == 200 and r.json()["cat"] == str(cats["其他收入"].id) and r.json()["kind"] == "income"
    r = api.patch("/api/transactions/%d" % t.id, headers=h, json={"kind": "expense", "cat": str(cats["餐飲"].id)})
    assert r.status_code == 200 and r.json()["cat"] == str(cats["餐飲"].id)


@pytest.mark.route(*PATCH)
def test_update_transaction_擋下來的情況(api):
    me, other = user("d@x.tw", "爸爸"), user("o@x.tw", "別人")
    cats = categories()
    g = ledger_of(me)
    done = ledger_of(me, name="已結算", kind="temp", settled_at=now())
    theirs = ledger_of(other, name="別人的")
    t = spend(me, g, cats["餐飲"], 100)
    locked = spend(me, done, cats["餐飲"], 100)
    not_mine = spend(other, theirs, cats["餐飲"], 100)
    h = login(me)
    url = "/api/transactions/%d"
    assert api.patch(url % t.id, headers=h, json={}).status_code == 400
    assert api.patch(url % t.id, headers=h, json={"source": "nlp"}).status_code == 422
    assert api.patch(url % t.id, headers=h, json={"date": "9/1"}).status_code == 400
    assert api.patch(url % not_mine.id, headers=h, json={"amount": 1}).status_code == 403
    assert api.patch(url % 99999, headers=h, json={"amount": 1}).status_code == 404
    assert api.patch(url % locked.id, headers=h, json={"amount": 1}).status_code == 409
    assert api.patch(url % t.id, headers=h, json={"groupId": str(done.id)}).status_code == 409
    assert api.patch(url % t.id, headers=h, json={"groupId": str(theirs.id)}).status_code == 403
    assert str(crud.get(Transaction, t.id).amount) == "100.00"


@pytest.mark.route(*PATCH)
def test_update_transaction_段落記帳的修改記進_user_corrected(api):
    me = user("d@x.tw", "爸爸")
    cats = categories()
    g = ledger_of(me)
    t = spend(me, g, cats["餐飲"], 55, source="nlp")
    crud.save(NlpParse, {"transaction_id": t.id, "user_id": me.id, "raw_text": "早餐55"})
    r = api.patch("/api/transactions/%d" % t.id, headers=login(me), json={"amount": 65})
    assert r.status_code == 200 and r.json()["raw"] == "早餐55"
    assert crud.get(NlpParse, where={"transaction_id": t.id}).user_corrected == {"amount": 65.0}


# ===========================================================================
# DELETE /api/transactions/{tx_id}
# ===========================================================================
DEL = ("DELETE", "/api/transactions/{tx_id}")


@pytest.mark.route(*DEL)
def test_delete_transaction_刪自己的_通知一起刪_解析紀錄留著(api):
    me, mom = user("k@x.tw", "小華"), user("m@x.tw", "媽媽")
    cats = categories()
    g = ledger_of(me)
    t = spend(me, g, cats["餐飲"], 55, source="nlp")
    crud.save(Notification, {"recipient_id": mom.id, "actor_id": me.id, "transaction_id": t.id, "type": "ward_transaction"})
    crud.save(NlpParse, {"transaction_id": t.id, "user_id": me.id, "raw_text": "早餐55"})
    r = api.delete("/api/transactions/%d" % t.id, headers=login(me))
    assert r.status_code == 200 and r.json() == {"deleted": str(t.id)}
    assert crud.count(Transaction) == 0 and crud.count(Notification) == 0
    assert crud.get(NlpParse, where={"raw_text": "早餐55"}).transaction_id is None
    assert api.delete("/api/transactions/%d" % t.id, headers=login(me)).status_code == 404


@pytest.mark.route(*DEL)
def test_delete_transaction_別人的_結算過的(api):
    me, other = user("d@x.tw", "爸爸"), user("o@x.tw", "別人")
    cats = categories()
    done = ledger_of(me, kind="temp", settled_at=now())
    theirs = ledger_of(other, name="別人的")
    locked = spend(me, done, cats["餐飲"], 1)
    not_mine = spend(other, theirs, cats["餐飲"], 1)
    assert api.delete("/api/transactions/%d" % not_mine.id, headers=login(me)).status_code == 403
    assert api.delete("/api/transactions/%d" % locked.id, headers=login(me)).status_code == 409
    assert crud.count(Transaction) == 2


# ===========================================================================
# DELETE /api/transactions?ids=
# ===========================================================================
BATCH = ("DELETE", "/api/transactions")


@pytest.mark.route(*BATCH)
def test_delete_transactions_全部通過才刪(api):
    me, other = user("d@x.tw", "爸爸"), user("o@x.tw", "別人")
    cats = categories()
    g = ledger_of(me, other)
    a, b = spend(me, g, cats["餐飲"], 1), spend(me, g, cats["餐飲"], 2)
    theirs = spend(other, g, cats["餐飲"], 3)
    h = login(me)
    assert api.delete("/api/transactions", headers=h).status_code == 400
    assert api.delete("/api/transactions?ids=%20,%20", headers=h).status_code == 400
    r = api.delete("/api/transactions?ids=%d,%d" % (a.id, theirs.id), headers=h)
    assert r.status_code == 403 and "一筆都沒有刪" in r.json()["detail"]
    r = api.delete("/api/transactions?ids=%d,99999" % a.id, headers=h)
    assert r.status_code == 404 and "99999" in r.json()["detail"]
    assert crud.count(Transaction) == 3
    r = api.delete("/api/transactions?ids=%d,%d,%d" % (b.id, a.id, b.id), headers=h)
    assert r.status_code == 200 and r.json() == {"deleted": [str(b.id), str(a.id)]}
    assert [t.id for t in crud.find(Transaction)] == [theirs.id]


@pytest.mark.route(*BATCH)
def test_delete_transactions_有結算過的就整批不刪(api):
    me = user("d@x.tw", "爸爸")
    cats = categories()
    g = ledger_of(me)
    done = ledger_of(me, name="已結算", kind="temp", settled_at=now())
    a, locked = spend(me, g, cats["餐飲"], 1), spend(me, done, cats["餐飲"], 1)
    r = api.delete("/api/transactions?ids=%d,%d" % (a.id, locked.id), headers=login(me))
    assert r.status_code == 409
    assert crud.count(Transaction) == 2
    ids = ",".join(str(i) for i in range(1, 102))
    assert api.delete("/api/transactions?ids=" + ids, headers=login(me)).status_code == 400
