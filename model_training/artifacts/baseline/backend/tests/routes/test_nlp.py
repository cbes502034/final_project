"""段落記帳：解析（不寫入）與確認後寫入（成員2）。模型用假的代替，不會真的連出去。"""

import pytest

from app.models import GroupMember, NlpParse, Notification, Transaction
from app.services.llm import client
from app.toolkit import crud
from tests.routes.conftest import categories, family_of, guard, ledger_of, login, now, today, user


@pytest.fixture()
def model(monkeypatch):
    """假的模型服務：reply 放要回的 JSON，calls 記下每一次收到的 prompt。"""
    box = {"reply": None, "calls": [], "error": None}

    def fake(prompt, **kwargs):
        box["calls"].append(prompt + "\n" + kwargs.get("system", ""))
        if box["error"]:
            raise client.ModelError(box["error"])
        return box["reply"]

    monkeypatch.setattr(client, "is_configured", lambda: True)
    monkeypatch.setattr(client, "complete_json", fake)
    return box


def _item(**kw):
    base = {"span": "早餐55", "date": today(), "amount": 55, "kind": "expense", "cat": None,
            "merchant": "", "note": "", "conf": {"date": 0.9, "amount": 0.99, "kind": 0.97, "cat": 0.8}}
    return {**base, **kw}


# ===========================================================================
# POST /api/nlp/parse
# ===========================================================================
ONE = ("POST", "/api/nlp/parse")


@pytest.mark.route(*ONE)
def test_parse_one_沒設定模型回_503_空白回_422(api, monkeypatch):
    monkeypatch.setattr(client, "is_configured", lambda: False)
    me = user("d@x.tw", "爸爸")
    assert api.post("/api/nlp/parse", headers=login(me), json={"text": "早餐55"}).status_code == 503
    assert api.post("/api/nlp/parse", headers=login(me), json={"text": "   "}).status_code == 422
    assert api.post("/api/nlp/parse", json={"text": "早餐55"}).status_code == 401


@pytest.mark.route(*ONE)
def test_parse_one_回傳_out_而且不寫資料庫(api, model):
    me = user("d@x.tw", "爸爸")
    cats = categories()
    model["reply"] = {"items": [_item(cat=str(cats["餐飲"].id), merchant="全家")]}
    r = api.post("/api/nlp/parse", headers=login(me), json={"text": " 早餐55 "})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["raw"] == "早餐55" and body["matched"] is False
    assert body["out"] == {"date": today(), "amount": 55, "kind": "expense", "cat": str(cats["餐飲"].id),
                           "merchant": "全家", "conf": 0.99, "catConf": 0.8}
    assert str(cats["餐飲"].id) in model["calls"][0] and today() in model["calls"][0]
    assert crud.count(Transaction) == 0 and crud.count(NlpParse) == 0


# ===========================================================================
# POST /api/nlp/parse-batch
# ===========================================================================
BATCH = ("POST", "/api/nlp/parse-batch")


@pytest.mark.route(*BATCH)
def test_parse_batch_每一欄都驗證_抽不到的放進_missing(api, model):
    me = user("d@x.tw", "爸爸")
    cats = categories()
    food, salary = str(cats["餐飲"].id), str(cats["薪資"].id)
    model["reply"] = {"items": [
        _item(span="早餐55", cat=food),
        _item(span="晚上加油", amount=None, cat=food),
        _item(span="亂編的", date="9/17", amount="abc", kind="gift", cat="999"),
        _item(span="收支對不上", cat=salary, conf={"date": 5, "amount": "x"}),
        "不是物件的一筆",
    ]}
    r = api.post("/api/nlp/parse-batch", headers=login(me), json={"text": "早餐55，晚上加油"})
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert [i["seq"] for i in items] == [1, 2, 3, 4]
    assert items[0]["missing"] == [] and items[0]["amount"] == 55 and items[0]["cat"] == food
    assert items[1]["missing"] == ["amount"] and items[1]["amount"] is None and items[1]["hint"]
    assert set(items[2]["missing"]) == {"date", "amount", "kind", "cat"}
    assert items[2]["date"] is None and items[2]["kind"] is None and items[2]["cat"] is None
    assert items[3]["missing"] == ["cat"]
    assert items[3]["conf"] == {"date": 1.0, "amount": 0.0, "kind": 0.0, "cat": 0.0}
    assert r.json()["raw"] == "早餐55，晚上加油"
    assert crud.count(Transaction) == 0


@pytest.mark.route(*BATCH)
def test_parse_batch_模型的問題一律_503(api, model, monkeypatch):
    me = user("d@x.tw", "爸爸")
    model["error"] = "模型服務沒有回應"
    assert api.post("/api/nlp/parse-batch", headers=login(me), json={"text": "早餐55"}).status_code == 503
    model["error"] = None
    model["reply"] = ["不是", "物件"]
    assert api.post("/api/nlp/parse-batch", headers=login(me), json={"text": "早餐55"}).status_code == 503
    monkeypatch.setattr(client, "is_configured", lambda: False)
    assert api.post("/api/nlp/parse-batch", headers=login(me), json={"text": "早餐55"}).status_code == 503
    assert api.post("/api/nlp/parse-batch", headers=login(me), json={"text": " "}).status_code == 422


# ===========================================================================
# POST /api/nlp/confirm
# ===========================================================================
CONFIRM = ("POST", "/api/nlp/confirm")


@pytest.mark.route(*CONFIRM)
def test_confirm_one_寫入明細與評測資料(api):
    me = user("d@x.tw", "爸爸")
    cats = categories()
    g = ledger_of(me)
    food = str(cats["餐飲"].id)
    r = api.post("/api/nlp/confirm", headers=login(me), json={
        "date": today(), "amount": 60, "kind": "expense", "cat": food, "raw": "早餐55", "conf": 0.99, "catConf": 0.9,
        "orig": {"by": "model", "date": today(), "amount": 55, "kind": "expense", "cat": food}})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["source"] == "nlp" and body["raw"] == "早餐55" and body["group"] == str(g.id)
    assert body["parsed"] == {"conf": 0.99, "catConf": 0.9}
    p = crud.get(NlpParse, where={"transaction_id": int(body["id"])})
    assert p.raw_text == "早餐55" and p.user_corrected == {"amount": 60}
    assert p.parsed_json["amount"] == 55 and p.model_ver != "rules"


@pytest.mark.route(*CONFIRM)
def test_confirm_one_規則解析的不算模型成績_錯誤情況(api):
    me = user("d@x.tw", "爸爸")
    cats = categories()
    ledger_of(me)
    food, salary = str(cats["餐飲"].id), str(cats["薪資"].id)
    base = {"date": today(), "amount": 55, "kind": "expense", "cat": food, "raw": "早餐55"}
    r = api.post("/api/nlp/confirm", headers=login(me), json={
        **base, "orig": {"by": "rules", "date": today(), "amount": 55, "kind": "expense", "cat": food}})
    assert r.status_code == 201, r.text
    p = crud.get(NlpParse, where={"transaction_id": int(r.json()["id"])})
    assert p.model_ver == "rules" and p.user_corrected is None
    assert api.post("/api/nlp/confirm", headers=login(me), json={**base, "cat": salary}).status_code == 400
    assert api.post("/api/nlp/confirm", headers=login(me), json={**base, "date": "9/17"}).status_code == 422
    assert crud.count(Transaction) == 1


# ===========================================================================
# POST /api/nlp/confirm-batch
# ===========================================================================
CB = ("POST", "/api/nlp/confirm-batch")


@pytest.mark.route(*CB)
def test_confirm_batch_整批寫入_每筆都有評測資料與通知(api):
    kid, mom = user("k@x.tw", "小華"), user("m@x.tw", "媽媽")
    fam = family_of((mom, "parent"), (kid, "child"))
    guard(mom, kid)
    cats = categories(fam)
    ledger_of(kid, name="第一本")
    g = ledger_of(kid, name="旅遊")
    food, pet = str(cats["餐飲"].id), str(cats["寵物"].id)
    items = [
        {"span": "早餐55", "date": today(), "amount": 55, "kind": "expense", "cat": food, "groupId": str(g.id),
         "conf": {"date": 0.9, "amount": 0.99, "kind": 0.9, "cat": 0.8},
         "orig": {"by": "model", "date": today(), "amount": 55, "kind": "expense", "cat": pet},
         "seq": 1, "missing": [], "hint": ""},
        {"span": "飼料300", "date": today(), "amount": 300, "kind": "expense", "cat": pet},
    ]
    r = api.post("/api/nlp/confirm-batch", headers=login(kid), json={"items": items})
    assert r.status_code == 201, r.text
    assert r.json() == {"created": 2}
    rows = crud.find(Transaction, order_by="id")
    assert [(t.group_id, t.source, int(t.amount)) for t in rows] == [(g.id, "nlp", 55), (g.id, "nlp", 300)]
    parses = crud.find(NlpParse, order_by="id")
    assert [p.raw_text for p in parses] == ["早餐55", "飼料300"]
    assert parses[0].user_corrected == {"cat": food} and float(parses[0].confidence) == 0.99
    assert parses[1].parsed_json is None
    assert sorted((n.recipient_id, n.transaction_id) for n in crud.find(Notification)) == \
        [(mom.id, rows[0].id), (mom.id, rows[1].id)]


@pytest.mark.route(*CB)
def test_confirm_batch_有一筆不對就一筆都不寫(api):
    me, mom = user("d@x.tw", "爸爸"), user("m@x.tw", "媽媽")
    cats = categories()
    g = ledger_of(me, mom)
    crud.save(GroupMember, {"notify": True}, where={"group_id": g.id, "user_id": mom.id})
    food, salary = str(cats["餐飲"].id), str(cats["薪資"].id)
    ok = {"span": "早餐55", "date": today(), "amount": 55, "kind": "expense", "cat": food}
    h = login(me)
    r = api.post("/api/nlp/confirm-batch", headers=h, json={"items": [ok, {**ok, "cat": salary}]})
    assert r.status_code == 400 and "第 2 筆" in r.json()["detail"]
    r = api.post("/api/nlp/confirm-batch", headers=h, json={"items": [ok, {**ok, "date": "9/17"}]})
    assert r.status_code == 422 and "第 2 筆" in r.json()["detail"]
    assert api.post("/api/nlp/confirm-batch", headers=h, json={"items": []}).status_code == 422
    done = ledger_of(me, name="已結算", kind="temp", settled_at=now())
    r = api.post("/api/nlp/confirm-batch", headers=h, json={"items": [{**ok, "groupId": str(done.id)}]})
    assert r.status_code == 409
    assert crud.count(Transaction) == 0 and crud.count(NlpParse) == 0 and crud.count(Notification) == 0
    r = api.post("/api/nlp/confirm-batch", headers=h, json={"items": [ok, ok]})
    assert r.status_code == 201 and crud.count(Notification) == 2
