"""
每一支路由的驗收測試：做對了長什麼樣子。

===========================================================================
同一組測試跑兩次
===========================================================================
    [說明]  把 app/routers/ 每一支說明字串裡的【完整寫法】套上去跑（在記憶體裡套，不會改到你的檔案）
            ——保證說明裡的程式真的跑得動，說明跟程式不會走散
    [你的]  app/routers/ 裡你寫的那一支——還是 @stub 時自動跳過，拿掉 @stub 之後就會跑

    pytest tests/routes                                        全部
    pytest tests/routes -k create_transaction                  只跑一支（說明＋你的）
    pytest tests/routes -k "create_transaction and u4f60" -v    只看路由檔裡寫的那一支
                                                               （u4f60 是標籤「你的」的跳脫碼，
                                                                -k 直接打中文會 0 selected）

兩個都綠，就代表你那一支跟說明講的一樣。
資料庫是記憶體裡的 SQLite，每個測試一顆新的，不會動到你的資料。

===========================================================================
【完整寫法】怎麼被套上去
===========================================================================
每一支的說明字串都有同樣的格式：

    【完整寫法】
        第一步：把檔案最上面的 import 換成這樣 …        ← 換掉 from __future__ 之後、router = 之前那一段
        第二步：把整個 xxx 換成這段 …                    ← 換掉那一支（從 @router 到函式最後一行），說明字串留著
        第三步：打開 app/services/…，把 yyy() 換成這段    ← 有的才有：換掉那個服務函式

apply() 就是照這三步做一次。改了說明的格式，這裡跟著壞，所以格式不要自己發明。
"""

from __future__ import annotations

import ast
import functools
import importlib
import inspect
import io
import os
import textwrap
import types
from datetime import datetime, timedelta, timezone

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost/test")
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production-at-least-32-bytes-long")

import pytest  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import routers  # noqa: E402
from app.models import (  # noqa: E402
    Category, Family, FamilyMember, Group, GroupMember, Guardianship, SavingsGoal, Transaction, User,
)
from app.routers._stub import is_stub  # noqa: E402
from app.toolkit import crud, db, money, passwords, tokens  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(os.path.dirname(HERE))

SECTION_CODE = "【完整寫法】"
SECTION_CHECK = "【做完怎麼確認】"


# ===========================================================================
# 從說明字串拿出【完整寫法】
# ===========================================================================
def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _step_code(head: str, rest: list[str]) -> str:
    """「第N步：…」那一行後面：跟它同一層縮排的是說明，縮排更深的那一整段是程式。"""
    level = _indent(head)
    start = next(i for i, line in enumerate(rest) if line.strip() and _indent(line) > level)
    return textwrap.dedent("".join(rest[start:])).strip("\n") + "\n"


def parse_doc(doc: str) -> dict | None:
    """說明字串 → {imports, code, extra: [(檔案, 函式, 程式)]}。沒有【完整寫法】回 None。"""
    if SECTION_CODE not in doc:
        return None
    sec = doc[doc.index(SECTION_CODE):doc.index(SECTION_CHECK)]
    sec = sec[sec.index("\n") + 1:]
    steps: list[list[str]] = []
    for line in sec.splitlines(keepends=True):
        if line.strip().startswith(("第一步", "第二步", "第三步", "第四步")):
            steps.append([line])
        elif steps:
            steps[-1].append(line)
    out = {"imports": _step_code(steps[0][0], steps[0][1:]),
           "code": _step_code(steps[1][0], steps[1][1:]),
           "extra": []}
    for step in steps[2:]:
        head = step[0].strip()
        # 第三步：打開 app/services/analytics.py，把 summary() 整個換成這段
        path = head[head.index("app/"):].split("，")[0].strip()
        func = head[head.index("把 ") + 2:head.index("()")].strip()
        out["extra"].append((path, func, _step_code(step[0], step[1:])))
    return out


def apply(source: str) -> tuple[str, list]:
    """一個路由檔的原始碼 → 每一支都照【完整寫法】做完的原始碼，外加第三步要換的服務函式。

    做的就是組員照說明字串會做的那兩件事：
        · 刪掉 @stub
        · 把說明字串下面的內容（還沒做的就是 raise not_ready 那一行）換成第二步
    裝飾器、函式名稱、參數、說明字串都不動——第二步裡也只有函式內容。
    """
    tree = ast.parse(source)
    docs = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            doc = ast.get_docstring(node, clean=False)
            parsed = parse_doc(doc or "")
            if parsed:
                docs.append((node, parsed))
    if not docs:
        return source, []
    imports = {p["imports"] for _, p in docs}
    assert len(imports) == 1, "同一個檔案裡，每一支的第一步（import）要一模一樣"
    lines = source.splitlines(keepends=True)
    extra = []
    # 從檔尾往回換，前面的行號才不會跑掉
    for node, parsed in sorted(docs, key=lambda x: -x[0].lineno):
        body = parsed["code"]
        # 第二步只有函式內容（可能有 return），包成一個函式才解析得動
        ast.parse("def _():\n" + textwrap.indent(body, "    "))
        doc_node = node.body[0]
        ind = " " * doc_node.col_offset
        new_body = ["\n"] + [ind + line if line.strip() else line for line in body.splitlines(keepends=True)]
        lines[doc_node.end_lineno:node.end_lineno] = new_body      # 說明字串下面到函式結尾
        for deco in sorted(node.decorator_list, key=lambda d: -d.lineno):
            if ast.unparse(deco) == "stub":
                del lines[deco.lineno - 1]
        extra.extend(parsed["extra"])
    src = "".join(lines)
    # 第一步：換掉 import 區
    a = src.index("from __future__ import annotations\n") + len("from __future__ import annotations\n")
    b = src.index("router = APIRouter(")
    src = src[:a] + "\n" + imports.pop() + "\n" + src[b:]
    return src, extra


# ===========================================================================
# 兩個對象：照說明套好的 app、你寫的 app
# ===========================================================================
def _source(module: types.ModuleType) -> str:
    return io.open(module.__file__, encoding="utf-8").read()


@functools.lru_cache(maxsize=1)
def _documented():
    """(照說明套好的 app, 第三步的服務函式, 有完整寫法的路由)。整個測試只建一次。"""
    app = FastAPI()
    extra = []
    covered = set()
    for module in routers.ALL:
        src, more = apply(_source(module))
        extra.extend(more)
        mod = types.ModuleType("_documented_" + module.__name__.rsplit(".", 1)[-1])
        mod.__file__ = module.__file__
        exec(compile(src, module.__file__, "exec"), mod.__dict__)
        app.include_router(mod.router, prefix="/api")
        for route in mod.router.routes:
            doc = inspect.getdoc(route.endpoint) or ""
            if SECTION_CODE in doc:
                for method in route.methods:
                    covered.add((method, "/api" + route.path))
    # 第三步：同一個服務檔的函式放在同一個命名空間裡（parse_one 會呼叫換好的 parse_batch）
    spaces = {}
    for path, func, code in extra:
        target = importlib.import_module(path[:-3].replace("/", "."))
        ns = spaces.setdefault(path, dict(vars(target)))
        exec(compile(code, os.path.join(BACKEND, path), "exec"), ns)
    patches = []
    for path, func, _code in extra:
        target = importlib.import_module(path[:-3].replace("/", "."))
        patches.append((target, func, spaces[path][func]))
    return app, patches, frozenset(covered)


def _endpoint(app, method, path):
    for r in app.routes:
        if getattr(r, "path", None) == path and method in getattr(r, "methods", ()):
            return r.endpoint
    return None


@pytest.fixture(params=["說明", "你的"])
def api(request, monkeypatch):
    """回傳 TestClient。「說明」沒有完整寫法、「你的」還是 @stub，就跳過。"""
    route = request.node.get_closest_marker("route")
    assert route, "每一支測試都要標 @pytest.mark.route(方法, 路徑)"
    method, path = route.args
    if request.param == "說明":
        app, patches, covered = _documented()
        if (method, path) not in covered:
            pytest.skip("%s %s 的說明還沒有【完整寫法】" % (method, path))
        for target, name, fn in patches:
            monkeypatch.setattr(target, name, fn)
    else:
        from app.main import app
        if is_stub(_endpoint(app, method, path)):
            pytest.skip("%s %s 還沒做（拿掉 @stub 之後這裡就會跑）" % (method, path))
    original = str(db.engine.url)
    db.use_database("sqlite://")
    db.create_all()
    try:
        yield TestClient(app)
    finally:
        db.drop_all()
        db.use_database(original)


def pytest_configure(config):
    config.addinivalue_line("markers", "route(method, path): 這支測試驗的是哪一條路由")


# ===========================================================================
# 共用的準備工作
# ===========================================================================
PASSWORD = "pass1234"


@functools.lru_cache(maxsize=1)
def password_hash() -> str:
    return passwords.hash_password(PASSWORD)


def now():
    return datetime.now(timezone.utc)


def this_month() -> str:
    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m")


def today() -> str:
    return datetime.now(timezone(timedelta(hours=8))).date().isoformat()


def login(user):
    return {"Authorization": "Bearer " + tokens.make_access_token(user.id)}


def user(email, name, **extra):
    return crud.save(User, {"email": email, "password_hash": password_hash(), "display_name": name,
                            "theme": "paper", **extra})


def family_of(*members, name="王家"):
    """[(user, 'parent'|'child'), ...] 建一個家庭。"""
    fam = crud.save(Family, {"name": name, "created_by": members[0][0].id})
    crud.save(FamilyMember, [{"family_id": fam.id, "user_id": u.id, "role": r} for u, r in members])
    return fam


def guard(guardian, ward):
    return crud.save(Guardianship, {"guardian_id": guardian.id, "ward_id": ward.id, "created_by": guardian.id})


def ledger_of(owner, *others, name="家用", **extra):
    g = crud.save(Group, {"name": name, "created_by": owner.id, **extra})
    crud.save(GroupMember, [{"group_id": g.id, "user_id": u.id} for u in (owner,) + others])
    return g


def categories(family=None):
    """系統的「餐飲」「其他」「薪資」「其他收入」，以及（有家庭時）我們家自訂的「寵物」。"""
    rows = crud.save(Category, [
        {"name": "餐飲", "kind": "expense", "color": "cat-food"},
        {"name": "其他", "kind": "expense", "color": "cat-other"},
        {"name": "薪資", "kind": "income", "color": "cat-daily"},
        {"name": "其他收入", "kind": "income", "color": "cat-other"},
    ])
    out = {c.name: c for c in rows}
    if family is not None:
        out["寵物"] = crud.save(Category, {"name": "寵物", "kind": "expense", "color": "cat-other",
                                         "family_id": family.id})
    return out


def spend(who, group, cat, amount, day=None, kind=None, **extra):
    """直接寫一筆明細（不經過路由）。day 預設今天。"""
    return crud.save(Transaction, {
        "user_id": who.id, "group_id": group.id, "category_id": cat.id, "kind": kind or cat.kind,
        "amount": money.quantize(amount), "occurred_on": datetime.fromisoformat(day or today()).date(),
        "source": "manual", **extra})


def goal(who, amount, group=None, period=None):
    return crud.save(SavingsGoal, {"user_id": who.id, "group_id": group.id if group else None,
                                   "period_key": period or this_month(), "goal_amount": amount,
                                   "created_by": who.id})

