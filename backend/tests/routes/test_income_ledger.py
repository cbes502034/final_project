"""固定收入自動入帳：規則寫在 app/services/income_ledger.py 的開頭，這裡一條一條驗。"""
from datetime import date

import pytest

from app.models import Category, Notification, Transaction, User
from app.services import allowance_ledger
from app.toolkit import crud
from tests.routes.conftest import categories, ledger_of, login, spend, user

PATCH_ME = ("PATCH", "/api/auth/me")


def _fixed(monkeypatch, day, **extra):
    monkeypatch.setattr(allowance_ledger, "today", lambda: day)
    categories()
    return user("a@x.tw", "阿明", income_mode="fixed", expected_income=42000, income_type="salary", **extra)


def _auto(who):
    return crud.find(Transaction, {"user_id": who.id, "source": "income_auto"}, order_by="id")


@pytest.mark.route(*PATCH_ME)
def test_到了入帳日才記_同一個月只記一次_有通知(api, monkeypatch):
    me = _fixed(monkeypatch, date(2026, 10, 3), income_pay_day=5)
    api.get("/api/auth/me", headers=login(me))
    assert _auto(me) == []                                             # 5 號才入帳
    monkeypatch.setattr(allowance_ledger, "today", lambda: date(2026, 10, 5))
    api.get("/api/auth/me", headers=login(me))
    api.get("/api/auth/me", headers=login(me))
    rows = _auto(me)
    assert [(int(t.amount), t.kind, t.occurred_on) for t in rows] == [(42000, "income", date(2026, 10, 5))]
    assert crud.count(Notification, {"recipient_id": me.id, "type": "income"}) == 1
    s = api.get("/api/summary", headers=login(me)).json()
    assert (s["income"], s["expectedIncome"]["pending"]) == (42000, 0)  # 記了之後不會再用預計的加一次


@pytest.mark.route(*PATCH_ME)
def test_自己已經記了就略過_刪掉也不再補(api, monkeypatch):
    me = _fixed(monkeypatch, date(2026, 10, 10))
    salary = crud.get(Category, where={"name": "薪資", "kind": "income"})
    spend(me, ledger_of(me, personal_owner_id=me.id), salary, 42000, day="2026-10-02")
    api.get("/api/auth/me", headers=login(me))
    assert _auto(me) == []
    assert crud.get(User, me.id).income_posted_period == "2026-10"

    other = user("b@x.tw", "小美", income_mode="fixed", expected_income=30000, income_type="salary")
    api.get("/api/auth/me", headers=login(other))
    tx = _auto(other)[0]
    assert api.delete(f"/api/transactions/{tx.id}", headers=login(other)).status_code == 200
    api.get("/api/auth/me", headers=login(other))
    assert _auto(other) == []                                          # 刪掉就是這個月沒有
    monkeypatch.setattr(allowance_ledger, "today", lambda: date(2026, 11, 1))
    api.get("/api/auth/me", headers=login(other))
    assert len(_auto(other)) == 1                                      # 下個月照常


@pytest.mark.route(*PATCH_ME)
def test_自動估不記_入帳日可以設也會擋錯(api, monkeypatch):
    monkeypatch.setattr(allowance_ledger, "today", lambda: date(2026, 10, 20))
    categories()
    me = user("a@x.tw", "阿明", income_mode="auto", expected_income=42000, income_type="freelance")
    api.get("/api/auth/me", headers=login(me))
    assert _auto(me) == []                                             # 預估不是事實
    r = api.patch("/api/auth/me", headers=login(me), json={"incomeMode": "fixed", "incomePayDay": 25})
    assert r.status_code == 200 and r.json()["incomePayDay"] == 25
    assert api.get("/api/auth/me", headers=login(me)).json()["user"]["incomePayDay"] == 25
    for bad in (0, 29):
        assert api.patch("/api/auth/me", headers=login(me), json={"incomePayDay": bad}).status_code == 422
    assert api.patch("/api/auth/me", headers=login(me), json={"incomeType": "salary_end"}).status_code == 422


@pytest.mark.route(*PATCH_ME)
def test_先填金額再選日期_這個月那筆跟著新設定_手動改過就不動(api, monkeypatch):
    me = _fixed(monkeypatch, date(2026, 10, 20))
    api.get("/api/auth/me", headers=login(me))                         # 還沒選日期：照 1 號先記了
    assert [t.occurred_on for t in _auto(me)] == [date(2026, 10, 1)]
    assert api.patch("/api/auth/me", headers=login(me), json={"incomePayDay": 10}).status_code == 200
    assert [(t.occurred_on, int(t.amount)) for t in _auto(me)] == [(date(2026, 10, 10), 42000)]
    api.patch("/api/auth/me", headers=login(me), json={"incomePayDay": 25})
    assert _auto(me) == []                                             # 25 號還沒到：先拿掉
    monkeypatch.setattr(allowance_ledger, "today", lambda: date(2026, 10, 25))
    api.get("/api/auth/me", headers=login(me))
    tx = _auto(me)[0]
    assert tx.occurred_on == date(2026, 10, 25)
    assert api.patch(f"/api/transactions/{tx.id}", headers=login(me), json={"amount": 43500}).status_code == 200
    api.patch("/api/auth/me", headers=login(me), json={"expectedIncome": 50000})
    assert int(_auto(me)[0].amount) == 43500                           # 手動改過的那一筆不動
