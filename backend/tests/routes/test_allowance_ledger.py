"""零用金自動記帳、邀請進鈴鐺、活動目標金額到達通知。

零用金的規則寫在 app/services/allowance_ledger.py 的開頭；這裡一條一條驗。
"""
from datetime import date

import pytest

from app.models import Allowance, AllowancePayment, Notification, SavingsGoal, Transaction
from app.services import allowance_ledger
from app.toolkit import crud
from tests.routes.conftest import categories, family_of, guard, ledger_of, login, spend, user

PUT_ALLOWANCE = ("PUT", "/api/allowance")


def _fam():
    dad, mom, kid = user("d@x.tw", "爸爸"), user("m@x.tw", "媽媽"), user("k@x.tw", "小華")
    family_of((dad, "parent"), (mom, "parent"), (kid, "child"))
    guard(dad, kid)
    guard(mom, kid)
    return dad, mom, kid


def _notes(who, kind="allowance"):
    return [n.payload_json for n in crud.find(Notification, {"recipient_id": who.id, "type": kind}, order_by="id")]


@pytest.mark.route(*PUT_ALLOWANCE)
def test_發放日還沒到不發_到了第一次打開就補發(api, monkeypatch):
    dad, _, kid = _fam()
    monkeypatch.setattr(allowance_ledger, "today", lambda: date(2026, 10, 3))
    r = api.put("/api/allowance", headers=login(dad), json={"wardId": str(kid.id), "amount": 2000, "payDay": 10})
    assert r.status_code == 200 and r.json()["payDay"] == 10
    assert crud.get(Allowance, where={"ward_id": kid.id}).pay_day == 10
    assert crud.count(Transaction) == 0                                  # 10 號才發
    monkeypatch.setattr(allowance_ledger, "today", lambda: date(2026, 10, 10))
    assert api.get("/api/auth/me", headers=login(kid)).status_code == 200  # 孩子打開系統就會補發
    pays = crud.find(Transaction, {"source": "allowance"}, order_by="id")
    assert [(t.user_id, t.kind, int(t.amount), t.occurred_on) for t in pays] == [
        (dad.id, "expense", 2000, date(2026, 10, 10)), (kid.id, "income", 2000, date(2026, 10, 10))]
    assert pays[1].note == "爸爸給的零用金" and pays[0].note == "給小華的零用金"
    api.get("/api/auth/me", headers=login(dad))
    assert crud.count(Transaction) == 2                                  # 同一個月只發一次
    for bad in (0, 29, "5"):
        assert api.put("/api/allowance", headers=login(dad),
                       json={"wardId": str(kid.id), "amount": 2000, "payDay": bad}).status_code == 422


@pytest.mark.route(*PUT_ALLOWANCE)
def test_兩位家長各發各的_孩子收到兩則通知_改金額只調整原本那一對(api):
    dad, mom, kid = _fam()
    api.put("/api/allowance", headers=login(dad), json={"wardId": str(kid.id), "amount": 2000})
    api.put("/api/allowance", headers=login(mom), json={"wardId": str(kid.id), "amount": 500})
    assert sorted(int(t.amount) for t in crud.find(Transaction, {"user_id": kid.id})) == [500, 2000]
    assert [(n["action"], n["payerName"], n["amount"]) for n in _notes(kid)] == [("paid", "爸爸", 2000), ("paid", "媽媽", 500)]
    api.put("/api/allowance", headers=login(mom), json={"wardId": str(kid.id), "amount": 800})
    assert crud.count(Transaction) == 4
    assert sorted(int(t.amount) for t in crud.find(Transaction, {"user_id": kid.id})) == [800, 2000]
    assert _notes(kid)[-1] == {"action": "adjusted", "amount": 800.0, "prev": 500.0, "payerName": "媽媽",
                               "period": _notes(kid)[-1]["period"]}
    # 家庭模式：家長給孩子是家裡換手，不算支出；爸爸自己的個人總覽照樣算
    fam = api.get("/api/summary?scope=family", headers=login(dad)).json()
    assert fam["expense"] == 0 and fam["income"] == 0
    assert api.get("/api/summary", headers=login(dad)).json()["expense"] == 2000
    goal = api.get("/api/family", headers=login(dad)).json()["family"]["goal"]
    assert goal["expense"] == 0


@pytest.mark.route("DELETE", "/api/transactions/{tx_id}")
def test_家長刪掉自己那筆_孩子那筆一起刪_這個月不再補發(api):
    dad, _, kid = _fam()
    api.put("/api/allowance", headers=login(dad), json={"wardId": str(kid.id), "amount": 2000})
    mine = crud.get(Transaction, where={"user_id": dad.id, "source": "allowance"})
    theirs = crud.get(Transaction, where={"user_id": kid.id, "source": "allowance"})
    assert api.delete(f"/api/transactions/{theirs.id}", headers=login(kid)).status_code == 409   # 孩子不能刪
    r = api.delete(f"/api/transactions/{mine.id}", headers=login(dad))
    assert r.status_code == 200, r.text
    assert crud.count(Transaction) == 0
    assert crud.get(AllowancePayment, where={"ward_id": kid.id}).status == "cancelled"
    assert _notes(kid)[-1]["action"] == "cancelled"
    api.get("/api/auth/me", headers=login(kid))
    assert crud.count(Transaction) == 0                                  # 取消就是這個月不發


@pytest.mark.route("PATCH", "/api/transactions/{tx_id}")
def test_孩子不能改_家長改金額孩子那筆跟著改(api):
    dad, _, kid = _fam()
    api.put("/api/allowance", headers=login(dad), json={"wardId": str(kid.id), "amount": 2000})
    mine = crud.get(Transaction, where={"user_id": dad.id, "source": "allowance"})
    theirs = crud.get(Transaction, where={"user_id": kid.id, "source": "allowance"})
    assert api.patch(f"/api/transactions/{theirs.id}", headers=login(kid), json={"amount": 9999}).status_code == 409
    cats = categories()
    assert api.patch(f"/api/transactions/{mine.id}", headers=login(dad),
                     json={"cat": str(cats["餐飲"].id)}).status_code == 409   # 只能改金額、日期、備註
    r = api.patch(f"/api/transactions/{mine.id}", headers=login(dad), json={"amount": 1500})
    assert r.status_code == 200, r.text
    assert int(crud.get(Transaction, theirs.id).amount) == 1500
    assert (_notes(kid)[-1]["action"], _notes(kid)[-1]["prev"]) == ("adjusted", 2000.0)


@pytest.mark.route("POST", "/api/family/invites")
def test_用帳號邀請家人_對方鈴鐺有通知(api):
    dad, newbie = user("d@x.tw", "爸爸"), user("n@x.tw", "阿嬤")
    family_of((dad, "parent"))
    r = api.post("/api/family/invites", headers=login(dad), json={"userId": str(newbie.id), "role": "parent"})
    assert r.status_code == 201, r.text
    assert [(n["familyName"], n["inviterName"], n["role"]) for n in _notes(newbie, "family_invite")] == [("王家", "爸爸", "parent")]
    listed = api.get("/api/notifications", headers=login(newbie)).json()["notifications"]
    assert listed[0]["type"] == "family_invite" and listed[0]["inviteId"] == r.json()["id"]


@pytest.mark.route("POST", "/api/groups/{gid}/invites")
def test_用帳號邀請朋友進活動_對方鈴鐺有通知(api):
    me, friend = user("a@x.tw", "阿明"), user("f@x.tw", "小美")
    g = ledger_of(me, name="露營")
    r = api.post(f"/api/groups/{g.id}/invites", headers=login(me), json={"email": "f@x.tw", "label": "小美"})
    assert r.status_code in (200, 201), r.text
    assert [(n["groupName"], n["inviterName"]) for n in _notes(friend, "activity_invite")] == [("露營", "阿明")]


@pytest.mark.route("GET", "/api/notifications")
def test_活動目標金額_到了通知一次_改了目標再到再通知(api):
    me = user("a@x.tw", "阿明")
    g = ledger_of(me, name="露營")
    cats = categories()
    crud.save(SavingsGoal, {"user_id": me.id, "group_id": g.id, "goal_amount": 1000, "created_by": me.id})
    spend(me, g, cats["餐飲"], 600)
    api.get("/api/notifications", headers=login(me))
    assert _notes(me, "activity_target") == []
    spend(me, g, cats["餐飲"], 500)                                      # 沒有收入：比的是累計支出 1,100
    listed = api.get("/api/notifications", headers=login(me)).json()["notifications"]
    assert [(n["type"], n["metric"], n["value"], n["goal"]) for n in listed] == [("activity_target", "spent", 1100.0, 1000.0)]
    api.get("/api/notifications", headers=login(me))
    assert len(_notes(me, "activity_target")) == 1                       # 同一個目標只通知一次
    crud.save(SavingsGoal, {"user_id": me.id, "group_id": g.id, "goal_amount": 1100, "created_by": me.id})
    api.get("/api/notifications", headers=login(me))
    assert len(_notes(me, "activity_target")) == 2
