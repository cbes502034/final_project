"""
後端骨架的測試：資料表、增刪改查、路由守衛、還沒做的路由、設定檔、遷移。

===========================================================================
為什麼要測「骨架」
===========================================================================
四個人都會直接用 crud.py、guards.py、models/。這些東西壞掉，壞的是四個人的進度，
而且症狀會出現在別人的路由裡，很難追。所以骨架本身要先有測試撐著。

資料庫用 SQLite 記憶體（sqlite://）：不用裝 PostgreSQL 就能跑，一秒內跑完。
兩者行為的差異（連線池、外鍵檢查）在 toolkit/db.py 已經處理掉。
"""

import io
import json
import os
import re
import subprocess
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost/test")
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production-at-least-32-bytes-long")

import httpx  # noqa: E402
import pytest  # noqa: E402
from fastapi import Depends, FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import (  # noqa: E402
    JSON, BigInteger, Boolean, Date, DateTime, Integer, LargeBinary, Numeric, Text, UniqueConstraint, Uuid,
)
from sqlalchemy.exc import IntegrityError  # noqa: E402

from app import models  # noqa: E402
from app.models import (  # noqa: E402
    Category, Family, FamilyMember, Group, GroupMember, Guardianship, PasswordReset, Transaction, User,
)
from app.toolkit import crud, db, password_reset, tokens  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
REPO = os.path.dirname(BACKEND)


# ===========================================================================
# 共用：一顆乾淨的記憶體資料庫
# ===========================================================================
@pytest.fixture()
def sqlite():
    """每個測試一顆新的記憶體資料庫，結束換回原本的設定（別的測試檔不受影響）。"""
    original = str(db.engine.url)
    db.use_database("sqlite://")
    db.create_all()
    try:
        yield db
    finally:
        db.drop_all()
        db.use_database(original)


def _user(email="a@x.tw", name="小明", **extra):
    return crud.save(User, {"email": email, "password_hash": "x", "display_name": name, "theme": "paper", **extra})


def _ledger(owner, name="家用"):
    g = crud.save(Group, {"name": name, "created_by": owner.id})
    crud.save(GroupMember, {"group_id": g.id, "user_id": owner.id})
    return g


def _cat():
    cid = crud.get(Category, where={"name": "餐飲"}, fields="id")
    return cid or crud.save(Category, {"name": "餐飲", "kind": "expense", "color": "cat-food"}).id


def _tx(user, group, amount, day, kind="expense", **extra):
    return crud.save(Transaction, {"user_id": user.id, "group_id": group.id, "category_id": _cat(), "kind": kind,
                                   "amount": Decimal(amount), "occurred_on": day, **extra})


# ===========================================================================
# models —— 跟 data.js 的 schema 一欄一欄對齊
# ===========================================================================
def _schema():
    script = ("global.window = {};require(process.argv[1]);"
              "process.stdout.write(JSON.stringify({schema: window.DATA.schema, relations: window.DATA.relations}));")
    out = subprocess.run(["node", "-e", script, os.path.join(REPO, "frontend", "js", "data.js")],
                         capture_output=True, check=True)
    return json.loads(out.stdout.decode("utf-8"))


SCHEMA = _schema()

_TYPES = {
    "BIGSERIAL": BigInteger, "BIGINT": BigInteger, "INT": Integer, "TEXT": Text, "BOOLEAN": Boolean,
    "TIMESTAMPTZ": DateTime, "DATE": Date, "BYTEA": LargeBinary, "JSONB": JSON, "UUID": Uuid,
}


def test_data_js_的每一張表都有模型_反過來也是():
    assert {t["t"] for t in SCHEMA["schema"]} == set(models.TABLES)
    assert set(models.TABLES) == set(db.Base.metadata.tables)


def test_每一欄的名字與型別都跟_data_js_一致():
    """改了 data.js 的 schema 沒改 models（或反過來）就紅燈。改欄位三處一起改：data.js → models → Alembic。"""
    problems = []
    for t in SCHEMA["schema"]:
        table = db.Base.metadata.tables[t["t"]]
        want = [c[0] for c in t["cols"]]
        have = [c.name for c in table.columns]
        if want != have:
            problems.append("%s 欄位不一致：data.js %s／models %s" % (t["t"], want, have))
            continue
        for name, typ, _note in t["cols"]:
            col = table.columns[name]
            base = typ.split("(")[0]
            real = col.type
            real = getattr(real, "impl", real)
            if base == "NUMERIC":
                ok = isinstance(real, Numeric)
                m = re.match(r"NUMERIC\((\d+),(\d+)\)", typ)
                if m and ok:
                    ok = (real.precision, real.scale) == (int(m.group(1)), int(m.group(2)))
            else:
                ok = isinstance(real, _TYPES[base])
            if base == "TIMESTAMPTZ" and ok:
                ok = real.timezone is True
            if not ok:
                problems.append("%s.%s：data.js 是 %s，models 是 %r" % (t["t"], name, typ, col.type))
    assert not problems, "\n".join(problems)


def test_主鍵與唯一鍵照_data_js_的說明():
    for t in SCHEMA["schema"]:
        table = db.Base.metadata.tables[t["t"]]
        for name, _typ, note in t["cols"]:
            col = table.columns[name]
            if re.match(r"^PK\b", note):
                assert col.primary_key, "%s.%s 應該是主鍵" % (t["t"], name)
            uniques = [sorted(x.name for x in c.columns) for c in table.constraints if isinstance(c, UniqueConstraint)]
            combo = re.search(r"UNIQUE\s*\(([^)]+)\)", note)
            if combo:                                    # 複合唯一：UNIQUE (recipient_id, transaction_id)
                cols = sorted(x.strip() for x in combo.group(1).split(","))
                assert cols in uniques, "%s 說明寫 UNIQUE (%s)，但 models 沒有這個複合唯一鍵" % (t["t"], combo.group(1))
            elif "UNIQUE" in note:
                assert col.unique or [name] in uniques, "%s.%s 說明寫 UNIQUE，但 models 沒設 unique" % (t["t"], name)


def test_外鍵跟_data_js_的說明一欄一欄對得起來():
    """說明寫「FK → users」的欄位，models 就要有指向 users 的外鍵；反過來 models 的外鍵也要寫在說明裡。"""
    problems = []
    for t in SCHEMA["schema"]:
        table = db.Base.metadata.tables[t["t"]]
        for name, _typ, note in t["cols"]:
            want = re.findall(r"FK → (\w+)", note)
            have = [fk.column.table.name for fk in table.columns[name].foreign_keys]
            if sorted(want) != sorted(have):
                problems.append("%s.%s：說明 %s／models %s" % (t["t"], name, want, have))
    assert not problems, "\n".join(problems)


def test_關聯圖上的每一條線都真的有外鍵():
    """data.js 的 relations 是畫在手冊上的關聯圖（挑重點畫，不是每個外鍵都畫）——畫了的一定要存在。"""
    have = {(tb.name, fk.column.table.name) for tb in db.Base.metadata.tables.values() for fk in tb.foreign_keys}
    missing = {(a, b) for a, b, *_ in SCHEMA["relations"]} - have
    assert not missing, "關聯圖有畫、models 沒有外鍵：%s" % sorted(missing)


def _data_js(name: str):
    """讀 data.js 裡的一份清單（node 跑一次，拿 JSON 回來）。"""
    out = subprocess.run(["node", "-e", "global.window={};require(process.argv[1]);"
                          "process.stdout.write(JSON.stringify(window.DATA[process.argv[2]]))",
                          os.path.join(REPO, "frontend", "js", "data.js"), name],
                         capture_output=True, check=True)
    return json.loads(out.stdout.decode("utf-8"))


def test_系統預設分類跟_data_js_一致():
    from app.cli import SYSTEM_CATEGORIES
    front = [(c["name"], c["kind"], c["color"]) for c in _data_js("categories")]
    assert [tuple(c) for c in SYSTEM_CATEGORIES] == front


def test_固定清單跟_data_js_一致():
    """app/catalog.py 是後端要回給前端的那幾份固定清單，正本是 data.js——走散了畫面就對不上。

    ⚠️ 分類的圖示字（icon）資料表沒有欄位，GET /api/categories 從 catalog 補，所以也要一起比。
    """
    from app import catalog

    assert catalog.FINANCE_STYLES == _data_js("financeStyles")
    assert catalog.FINANCE_GOALS == _data_js("financeGoals")
    assert catalog.FINANCE_HABITS == _data_js("financeHabits")
    assert catalog.ROLES == _data_js("roles")
    assert catalog.PERMISSIONS == _data_js("permissions")
    assert catalog.ADVICE_RULES == _data_js("adviceRules")
    assert list(catalog.GROUP_COLORS) == [c["id"] for c in _data_js("groupColors")]
    assert catalog.SAVINGS_RULE_NOTE == _data_js("savingsRule")["note"]
    assert [(c["name"], c["kind"], c["color"], c["icon"]) for c in _data_js("categories")] == \
        [tuple(row) for row in catalog.SYSTEM_CATEGORIES]
    assert catalog.CATEGORY_ICONS["餐飲"] == "食"


# ===========================================================================
# crud —— 五支函式、參數決定做什麼
# ===========================================================================
def test_新增一筆會拿到_id_預設值也有填(sqlite):
    u = _user()
    assert isinstance(u.id, int)
    assert u.is_platform_admin is False and u.created_at is not None


def test_get_用主鍵_用條件_只拿一個欄位_拿幾個欄位(sqlite):
    u = _user(email="ming@x.tw")
    assert crud.get(User, u.id).email == "ming@x.tw"
    assert crud.get(User, where={"email": "ming@x.tw"}, fields="id") == u.id
    assert crud.get(User, u.id, fields=("email", "display_name")) == {"email": "ming@x.tw", "display_name": "小明"}
    assert crud.get(User, 999) is None


def test_get_找不到可以直接丟例外(sqlite):
    from app.toolkit import errors
    with pytest.raises(crud.NotFound):
        crud.get(User, 999, missing="raise")
    with pytest.raises(Exception) as e:
        crud.get(User, 999, missing=errors.not_found("找不到這個人"))
    assert e.value.status_code == 404


def test_get_沒有_id_也沒有條件會被擋():
    with pytest.raises(ValueError):
        crud.get(User)


def test_find_的條件運算子(sqlite):
    u = _user()
    g = _ledger(u)
    for amt, day, note in [(100, date(2026, 9, 1), "早餐"), (250, date(2026, 9, 5), "午餐"), (900, date(2026, 8, 30), "Taxi")]:
        _tx(u, g, amt, day, note=note)
    ids = lambda where: sorted(int(r.amount) for r in crud.find(Transaction, where))  # noqa: E731
    assert ids({"amount__gte": 250}) == [250, 900]
    assert ids({"amount__lt": 250}) == [100]
    assert ids({"amount__ne": 100}) == [250, 900]
    assert ids({"amount__in": [100, 900]}) == [100, 900]
    assert ids({"amount__notin": [100]}) == [250, 900]
    assert ids({"note__contains": "餐"}) == [100, 250]
    assert ids({"note__icontains": "taxi"}) == [900]
    assert ids({"note__startswith": "早"}) == [100]
    assert ids({"occurred_on__between": (date(2026, 9, 1), date(2026, 9, 30))}) == [100, 250]
    assert ids({"merchant__isnull": True}) == [100, 250, 900]
    assert ids({"or": [{"amount": 100}, {"note": "Taxi"}]}) == [100, 900]
    assert ids([Transaction.amount > 200]) == [250, 900]


def test_欄位名字打錯會講出是哪張表哪個欄位():
    with pytest.raises(ValueError) as e:
        crud.build_where(Transaction, {"amout__gte": 1})
    assert "amout" in str(e.value) and "Transaction" in str(e.value)


def test_find_排序_分頁_只數筆數_只取欄位(sqlite):
    u = _user()
    g = _ledger(u)
    for i in range(1, 8):
        _tx(u, g, i * 10, date(2026, 9, i))
    rows = crud.find(Transaction, {"user_id": u.id}, order_by="-occurred_on", limit=2)
    assert [r.occurred_on.day for r in rows] == [7, 6]
    page = crud.find(Transaction, {"user_id": u.id}, order_by="occurred_on", page=2, size=3)
    assert page["total"] == 7 and page["pages"] == 3 and page["page"] == 2
    assert [r.occurred_on.day for r in page["items"]] == [4, 5, 6]
    assert crud.find(Transaction, {"user_id": u.id}, count=True) == 7 == crud.count(Transaction, {"user_id": u.id})
    assert crud.exists(Transaction, {"amount": 70}) and not crud.exists(Transaction, {"amount": 71})
    assert crud.find(Transaction, {"amount__lte": 20}, fields="amount", order_by="amount") == [10, 20]
    assert crud.find(Transaction, {"amount": 10}, fields=("kind", "amount")) == [{"kind": "expense", "amount": 10}]


def test_find_as_dict_的_id_是字串而且沒有機密欄位(sqlite):
    _user()
    row = crud.find(User, as_dict=True)[0]
    assert isinstance(row["id"], str)
    assert "password_hash" not in row and "avatar_bytes" not in row


def test_save_一次新增很多筆(sqlite):
    u = _user()
    g = _ledger(u)
    rows = crud.save(Transaction, [{"user_id": u.id, "group_id": g.id, "category_id": _cat(), "kind": "expense",
                                    "amount": 1, "occurred_on": date(2026, 9, 1)}] * 3)
    assert len(rows) == 3 and all(r.id for r in rows)


def test_save_帶主鍵是修改_找不到丟例外(sqlite):
    u = _user()
    crud.save(User, {"id": u.id, "display_name": "大明"})
    assert crud.get(User, u.id, fields="display_name") == "大明"
    with pytest.raises(crud.NotFound):
        crud.save(User, {"id": 999, "display_name": "誰"})


def test_save_用條件改很多筆_回傳改了幾筆(sqlite):
    u = _user()
    g = _ledger(u)
    _tx(u, g, 1, date(2026, 9, 1))
    _tx(u, g, 2, date(2026, 9, 2))
    assert crud.save(Transaction, {"note": "改過"}, where={"user_id": u.id}) == 2
    assert crud.find(Transaction, {"note": "改過"}, count=True) == 2


def test_save_upsert_有就改_沒有就新增(sqlite):
    u = _user()
    fam = crud.save(Family, {"name": "王家", "created_by": u.id})
    a = crud.save(FamilyMember, {"role": "parent"}, where={"family_id": fam.id, "user_id": u.id}, upsert=True)
    assert a.role == "parent"
    b = crud.save(FamilyMember, {"role": "child"}, where={"family_id": fam.id, "user_id": u.id}, upsert=True)
    assert b.role == "child" and crud.count(FamilyMember) == 1


def test_save_複合主鍵的表帶主鍵就是新增(sqlite):
    u = _user()
    fam = crud.save(Family, {"name": "王家", "created_by": u.id})
    crud.save(FamilyMember, {"family_id": fam.id, "user_id": u.id, "role": "parent"})
    assert crud.get(FamilyMember, (fam.id, u.id)).role == "parent"
    crud.save(FamilyMember, {"family_id": fam.id, "user_id": u.id, "role": "child"})
    assert crud.get(FamilyMember, (fam.id, u.id), fields="role") == "child"


def test_沒有條件的修改與刪除會被擋(sqlite):
    _user()
    with pytest.raises(ValueError):
        crud.save(User, {"theme": "x"}, where={})
    with pytest.raises(ValueError):
        crud.remove(User)
    assert crud.save(User, {"theme": "x"}, where={}, allow_all=True) == 1


def test_remove_真刪與軟刪除(sqlite):
    u = _user()
    g = _ledger(u)
    t1, t2 = _tx(u, g, 1, date(2026, 9, 1)), _tx(u, g, 2, date(2026, 9, 2))
    assert crud.remove(Transaction, id=t1.id) == 1
    assert crud.remove(Transaction, {"id__in": [t2.id], "user_id": 999}) == 0       # 條件疊加：不是他的刪不掉
    assert crud.remove(Group, id=g.id, soft="archived_at") == 1
    assert crud.get(Group, g.id).archived_at is not None
    w = _user(email="kid@x.tw")
    crud.save(Guardianship, {"guardian_id": u.id, "ward_id": w.id})
    assert crud.remove(Guardianship, {"ward_id": w.id}, soft={"ended_at": datetime.now(timezone.utc)}) == 1
    assert crud.count(Guardianship, {"ended_at__isnull": False}) == 1


def test_同一個交易裡出錯會全部退回(sqlite):
    u = _user()
    with pytest.raises(IntegrityError):
        with db.session_scope() as s:
            crud.save(Family, {"name": "王家", "created_by": u.id}, db=s)
            crud.save(User, {"email": "a@x.tw", "password_hash": "x", "display_name": "重複", "theme": "paper"}, db=s)
    assert crud.count(Family) == 0


def test_db_transaction_會把_session_塞進第一個參數(sqlite):
    @db.db_transaction
    def rename(s, uid, name):
        s.get(User, uid).display_name = name

    u = _user()
    rename(u.id, "阿明")
    assert crud.get(User, u.id, fields="display_name") == "阿明"


def test_外鍵在_SQLite_上也會檢查(sqlite):
    with pytest.raises(IntegrityError):
        crud.save(Group, {"name": "孤兒帳本", "created_by": 12345})


def test_to_dict_改名_加欄位_金額與日期轉成前端要的樣子(sqlite):
    u = _user()
    g = _ledger(u)
    tx = _tx(u, g, "180.50", date(2026, 9, 3))
    d = crud.to_dict(tx, rename={"occurred_on": "date", "user_id": "user"}, extra={"userName": "小明"})
    assert d["date"] == "2026-09-03" and d["user"] == str(u.id) and d["userName"] == "小明"
    assert d["amount"] == 180.5 and isinstance(d["id"], str)
    assert crud.to_dict(_tx(u, g, 200, date(2026, 9, 3)))["amount"] == 200


# ===========================================================================
# guards —— 擋在路由前面
# ===========================================================================
def _probe_app():
    from app.guards import (admin_required, block_admin, can_see_user, guard, guest_only, in_group,
                            login_required, own, parent_required, protect, token_required)

    a = FastAPI()

    @a.get("/me")
    @login_required
    def me_(me: User):
        return {"id": me.id, "role": me.family_role}

    @a.get("/parent")
    @parent_required
    def parent_():
        return {"ok": True}

    @a.get("/no-family")
    @protect(family=False)
    def nofam(me: User):
        return {"ok": True}

    @a.get("/admin")
    @admin_required
    def admin_():
        return {"ok": True}

    @a.get("/money")
    @block_admin
    def money_():
        return {"ok": True}

    @a.get("/setup-done")
    def onboarded(me=Depends(guard(onboarded=True))):
        return {"ok": True}

    @a.post("/register")
    @guest_only
    def register():
        return {"ok": True}

    @a.delete("/tx/{tx_id}")
    def delete_tx(tx=Depends(own(Transaction, "tx_id"))):
        return {"id": tx.id}

    @a.get("/groups/{gid}")
    def group_(g=Depends(in_group("gid"))):
        return {"id": g.id}

    @a.delete("/groups/{gid}")
    def group_del(g=Depends(in_group("gid", owner=True))):
        return {"id": g.id}

    @a.get("/users/{user_id}")
    def see(u=Depends(can_see_user("user_id"))):
        return {"id": u.id}

    @a.post("/reset")
    def reset(row=Depends(token_required())):
        return {"id": row.id}

    return TestClient(a)


def _auth(user):
    return {"Authorization": "Bearer " + tokens.make_access_token(user.id)}


def test_沒登入_壞掉的權杖_被停權(sqlite):
    c = _probe_app()
    assert c.get("/me").status_code == 401
    assert c.get("/me", headers={"Authorization": "Bearer nope"}).status_code == 401
    u = _user()
    assert c.get("/me", headers=_auth(u)).json() == {"id": u.id, "role": None}
    crud.save(User, {"id": u.id, "suspended_at": datetime.now(timezone.utc), "suspended_reason": "測試"})
    r = c.get("/me", headers=_auth(u))
    assert r.status_code == 403 and "停權" in r.text


def test_帳號被刪掉之後舊權杖不能用(sqlite):
    c = _probe_app()
    u = _user()
    h = _auth(u)
    crud.remove(User, id=u.id)
    assert c.get("/me", headers=h).status_code == 401


def test_家庭角色與有沒有家庭(sqlite):
    c = _probe_app()
    dad, kid, loner = _user("dad@x.tw"), _user("kid@x.tw"), _user("solo@x.tw")
    fam = crud.save(Family, {"name": "王家", "created_by": dad.id})
    crud.save(FamilyMember, [{"family_id": fam.id, "user_id": dad.id, "role": "parent"},
                             {"family_id": fam.id, "user_id": kid.id, "role": "child"}])
    assert c.get("/me", headers=_auth(dad)).json()["role"] == "parent"
    assert c.get("/parent", headers=_auth(dad)).status_code == 200
    assert c.get("/parent", headers=_auth(kid)).status_code == 403
    assert c.get("/parent", headers=_auth(loner)).status_code == 403
    assert c.get("/no-family", headers=_auth(loner)).status_code == 200
    assert c.get("/no-family", headers=_auth(dad)).status_code == 409
    crud.save(FamilyMember, {"status": "removed"}, where={"user_id": kid.id})
    assert c.get("/me", headers=_auth(kid)).json()["role"] is None      # 移出家庭就不算


def test_平台管理員與財務路由(sqlite):
    c = _probe_app()
    admin, user = _user("admin@x.tw", is_platform_admin=True), _user("u@x.tw")
    assert c.get("/admin", headers=_auth(admin)).status_code == 200
    assert c.get("/admin", headers=_auth(user)).status_code == 403
    assert c.get("/money", headers=_auth(user)).status_code == 200
    assert c.get("/money", headers=_auth(admin)).status_code == 403


def test_個人化設定與只給沒登入的人(sqlite):
    c = _probe_app()
    u = _user()
    assert c.get("/setup-done", headers=_auth(u)).status_code == 403
    crud.save(User, {"id": u.id, "onboarded_at": datetime.now(timezone.utc)})
    assert c.get("/setup-done", headers=_auth(u)).status_code == 200
    assert c.post("/register").status_code == 200
    assert c.post("/register", headers={"Authorization": "Bearer expired.or.broken"}).status_code == 200
    assert c.post("/register", headers=_auth(u)).status_code == 400


def test_只能動自己的紀錄(sqlite):
    c = _probe_app()
    me, other = _user("me@x.tw"), _user("other@x.tw")
    g = _ledger(me)
    mine = _tx(me, g, 1, date(2026, 9, 1))
    theirs = _tx(other, g, 1, date(2026, 9, 1))
    assert c.delete("/tx/%d" % mine.id, headers=_auth(me)).status_code == 200
    assert c.delete("/tx/%d" % theirs.id, headers=_auth(me)).status_code == 403
    assert c.delete("/tx/99999", headers=_auth(me)).status_code == 404
    assert c.delete("/tx/abc", headers=_auth(me)).status_code == 404


def test_帳本成員與建立者(sqlite):
    c = _probe_app()
    owner, member, stranger = _user("o@x.tw"), _user("m@x.tw"), _user("s@x.tw")
    g = _ledger(owner)
    crud.save(GroupMember, {"group_id": g.id, "user_id": member.id})
    assert c.get("/groups/%d" % g.id, headers=_auth(member)).status_code == 200
    assert c.get("/groups/%d" % g.id, headers=_auth(stranger)).status_code == 403
    assert c.delete("/groups/%d" % g.id, headers=_auth(member)).status_code == 403
    assert c.delete("/groups/%d" % g.id, headers=_auth(owner)).status_code == 200
    crud.remove(Group, id=g.id, soft="removed_at")
    assert c.get("/groups/%d" % g.id, headers=_auth(owner)).status_code == 404      # 移除的帳本當作不存在


def test_看得到誰_監管_同家庭家長_同帳本(sqlite):
    c = _probe_app()
    mom, dad, kid, friend, stranger = (_user(e) for e in ("mom@x.tw", "dad@x.tw", "kid@x.tw", "f@x.tw", "s@x.tw"))
    fam = crud.save(Family, {"name": "王家", "created_by": mom.id})
    crud.save(FamilyMember, [{"family_id": fam.id, "user_id": mom.id, "role": "parent"},
                             {"family_id": fam.id, "user_id": dad.id, "role": "parent"},
                             {"family_id": fam.id, "user_id": kid.id, "role": "child"}])
    assert c.get("/users/%d" % dad.id, headers=_auth(mom)).status_code == 200      # 同家庭家長
    assert c.get("/users/%d" % kid.id, headers=_auth(mom)).status_code == 403      # 沒有監管關係
    crud.save(Guardianship, {"guardian_id": mom.id, "ward_id": kid.id})
    assert c.get("/users/%d" % kid.id, headers=_auth(mom)).status_code == 200
    assert c.get("/users/%d" % mom.id, headers=_auth(kid)).status_code == 403      # 被監管的看不到家長
    g = _ledger(mom, "旅行")
    crud.save(GroupMember, {"group_id": g.id, "user_id": friend.id})
    assert c.get("/users/%d" % friend.id, headers=_auth(mom)).status_code == 200   # 同帳本
    assert c.get("/users/%d" % stranger.id, headers=_auth(mom)).status_code == 403
    assert c.get("/users/99999", headers=_auth(mom)).status_code == 404


def test_一次性連結_找不到_過期_用過都回同一句(sqlite):
    c = _probe_app()
    u = _user()
    good, old, used = password_reset.new_token(), password_reset.new_token(), password_reset.new_token()
    now = datetime.now(timezone.utc)
    crud.save(PasswordReset, [
        {"user_id": u.id, "token_hash": password_reset.hash_token(good), "expires_at": now + timedelta(minutes=10)},
        {"user_id": u.id, "token_hash": password_reset.hash_token(old), "expires_at": now - timedelta(minutes=1)},
        {"user_id": u.id, "token_hash": password_reset.hash_token(used), "expires_at": now + timedelta(minutes=10),
         "used_at": now},
    ])
    assert c.post("/reset", json={"token": good}).status_code == 200
    bodies = {c.post("/reset", json={"token": t}).text for t in (old, used, password_reset.new_token(), "短")}
    assert len(bodies) == 1 and password_reset.INVALID_MESSAGE in bodies.pop()
    assert c.post("/reset", content=b"not json").status_code == 400


# ===========================================================================
# 真正的 app：還沒做的路由
# ===========================================================================
def test_還沒做的路由_沒登入先被守衛擋_登入後回_501_講出是哪一支誰負責(sqlite):
    from app.main import app

    c = TestClient(app)
    assert c.get("/api/family").status_code == 401
    u = _user()
    r = c.get("/api/family", headers=_auth(u))
    assert r.status_code == 501
    body = r.text
    assert "GET /api/family" in body and "成員4" in body


def test_每一支還沒做的路由都寫著自己的路徑與負責人():
    """raise not_ready("...") 裡的路徑、負責人，要跟掛上去的路徑、ownership.py 對得起來。"""
    import inspect as _inspect

    from app.main import app
    from app.ownership import owner_of
    from app.routers._stub import is_stub

    wrong = []
    for route in app.routes:
        endpoint = getattr(route, "endpoint", None)
        if not is_stub(endpoint):
            continue
        src = _inspect.getsource(_inspect.unwrap(endpoint))
        m = re.search(r'not_ready\("(\w+) ([^"]+)", OWNER\)', src)
        method = next(iter(route.methods - {"HEAD", "OPTIONS"}))
        owner = owner_of(method, route.path)
        module = _inspect.getmodule(_inspect.unwrap(endpoint))
        if not m or (m.group(1), m.group(2)) != (method, route.path) or owner is None or module.OWNER != owner.label:
            wrong.append("%s %s" % (method, route.path))
    assert not wrong, wrong


def test_進度表把還沒做的算成待辦():
    from app.ownership import progress

    p = progress()
    total = sum(len(v["done"]) + len(v["todo"]) for v in p.values())
    assert total == 70
    assert sum(len(v["todo"]) for v in p.values()) == 70     # 目前全部都還是 @stub


# ===========================================================================
# services —— 已經做好的共用部分
# ===========================================================================
def test_模型呼叫層_沒設定回_None_設定了會打_OpenAI_相容介面(monkeypatch):
    from app.services.llm import client as llm
    from app.toolkit.config import settings

    monkeypatch.setattr(settings, "model_base_url", "")
    assert llm.complete("hi") is None

    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"choices": [{"message": {"content": '```json\n{"amount": 80}\n```'}}]})

    monkeypatch.setattr(settings, "model_base_url", "http://model.test/")
    monkeypatch.setattr(settings, "model_api_key", "k")
    fake = httpx.Client(transport=httpx.MockTransport(handler))
    assert llm.complete_json("早餐 80", client=fake) == {"amount": 80}
    assert seen == {"url": "http://model.test/v1/chat/completions", "auth": "Bearer k"}


def test_模型服務壞掉會丟_ModelError_讓路由回_503(monkeypatch):
    from app.services.llm import client as llm
    from app.toolkit.config import settings

    monkeypatch.setattr(settings, "model_base_url", "http://model.test")
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(502)

    monkeypatch.setattr(llm.time, "sleep", lambda _s: None)
    with pytest.raises(llm.ModelError):
        llm.complete("x", client=httpx.Client(transport=httpx.MockTransport(handler)), retries=2)
    assert len(calls) == 3                                   # 5xx 會重試
    calls.clear()
    with pytest.raises(llm.ModelError):
        llm.complete("x", client=httpx.Client(transport=httpx.MockTransport(lambda r: calls.append(1) or httpx.Response(400))))
    assert len(calls) == 1                                   # 4xx 不重試


def test_存款狀態_跟前端同一套門檻():
    from app.services.analytics import savings_status

    assert savings_status(50000, 20000, 10000)["level"] == "safe"
    assert savings_status(50000, 33000, 10000)["level"] == "near"
    assert savings_status(50000, 42000, 10000)["level"] == "over"
    assert savings_status(0, 0, 0)["level"] == "safe"
    s = savings_status(50000, 42000, 10000)
    assert s["allowance"] == 40000 and s["shortfall"] == 2000 and s["actual"] == 8000


def test_評估指標():
    from app.services.evaluation import exact_match_rate, macro_f1

    pairs = [({"amount": 80, "cat": "餐飲"}, {"amount": 80, "cat": "餐飲"}),
             ({"amount": 80, "cat": "交通"}, {"amount": 80, "cat": "餐飲"})]
    assert exact_match_rate(pairs, ("amount",)) == 1.0
    assert exact_match_rate(pairs, ("amount", "cat")) == 0.5
    assert macro_f1([("a", "a"), ("b", "b")]) == 1.0
    assert exact_match_rate([], ("amount",)) == 0.0 and macro_f1([]) == 0.0


# ===========================================================================
# 設定檔與遷移
# ===========================================================================
def test_env_example_列出每一個設定_分成共用與四個成員_機密一律留空():
    from app.toolkit.config import Settings

    text = io.open(os.path.join(BACKEND, ".env.example"), encoding="utf-8").read()
    keys = dict(re.findall(r"^([A-Z_][A-Z0-9_]*)=(.*)$", text, re.M))
    assert set(keys) == {name.upper() for name in Settings.model_fields}
    for section in ("共用", "成員1", "成員2", "成員3", "成員4"):
        assert section in text
    for secret in ("JWT_SECRET", "BREVO_API_KEY", "MODEL_API_KEY", "MODEL_BASE_URL", "MAIL_FROM"):
        assert keys[secret].strip() == "", "%s 在 .env.example 裡不可以有值" % secret


def test_存款門檻前後端一致():
    """前端補 savings.level 用 data.js 的 savingsRule，後端用設定的門檻——兩邊不一樣，同一個人在總覽跟建議會看到不同的燈號。"""
    from app.toolkit.config import Settings

    out = subprocess.run(["node", "-e", "global.window={};require(process.argv[1]);"
                          "process.stdout.write(JSON.stringify(window.DATA.savingsRule))",
                          os.path.join(REPO, "frontend", "js", "data.js")], capture_output=True, check=True)
    rule = json.loads(out.stdout.decode("utf-8"))
    assert rule["warnAt"] == Settings.model_fields["savings_warn_ratio"].default
    assert rule["overAt"] == Settings.model_fields["savings_over_ratio"].default


def test_設定檔的每一段都標了是誰的():
    src = io.open(os.path.join(BACKEND, "app", "toolkit", "config.py"), encoding="utf-8").read()
    for section in ("共用", "成員1", "成員2", "成員3", "成員4"):
        assert re.search(r"^\s*# " + section, src, re.M), section


def test_遷移建出來的表跟_models_一模一樣(tmp_path):
    """alembic upgrade head 之後再比對一次 models：沒有差異才代表遷移檔跟得上。"""
    from alembic import command
    from alembic.autogenerate import compare_metadata
    from alembic.config import Config
    from alembic.migration import MigrationContext
    from sqlalchemy import create_engine

    url = "sqlite:///" + (tmp_path / "mig.db").as_posix()
    cfg = Config(os.path.join(BACKEND, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(BACKEND, "alembic"))
    cfg.cmd_opts = type("o", (), {"x": ["url=" + url]})()
    before = os.environ.get("DATABASE_URL")
    try:
        command.upgrade(cfg, "head")
        eng = create_engine(url)
        with eng.connect() as conn:
            diff = compare_metadata(MigrationContext.configure(conn, opts={"compare_type": True}), db.Base.metadata)
        eng.dispose()
        assert diff == [], "models 改了但沒有產生遷移：alembic revision --autogenerate -m '...'\n%s" % diff
        command.downgrade(cfg, "base")
    finally:
        if before is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = before


def test_alembic_ini_只能有英文():
    """Windows 的 alembic 用系統編碼（cp950）讀 .ini，裡面有中文就每個指令都壞。"""
    raw = io.open(os.path.join(BACKEND, "alembic.ini"), "rb").read()
    assert all(b < 128 for b in raw)


def test_沒接住的錯誤回_JSON_正式環境不帶內部細節(monkeypatch):
    """前端只讀 {"detail"}；正式環境不可以把例外訊息（可能有表名、SQL）送出去。"""
    from app.main import unexpected_error
    from app.toolkit.config import settings

    a = FastAPI()
    a.add_exception_handler(Exception, unexpected_error)

    @a.get("/boom")
    def boom():
        raise KeyError("users.password_hash")

    c = TestClient(a, raise_server_exceptions=False)
    monkeypatch.setattr(settings, "app_env", "development")
    r = c.get("/boom")
    assert r.status_code == 500 and "KeyError" in r.json()["detail"]
    monkeypatch.setattr(settings, "app_env", "production")
    r = c.get("/boom")
    assert r.status_code == 500 and r.json() == {"detail": "系統發生錯誤，請稍後再試"}


def test_正式環境不印_SQL(monkeypatch):
    from app.toolkit.config import settings

    monkeypatch.setattr(settings, "db_echo", True)
    monkeypatch.setattr(settings, "app_env", "production")
    assert db.make_engine("sqlite://").echo is False
    monkeypatch.setattr(settings, "app_env", "development")
    assert db.make_engine("sqlite://").echo is True
