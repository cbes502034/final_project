"""
前端 api.js 接真後端（http 模式）時的保證：前端代勞、備援、錯誤訊息指出是哪一支。

===========================================================================
為什麼放在後端的測試裡
===========================================================================
後端回什麼、前端怎麼補，是同一份契約的兩半。後端的人改了回應形狀或錯誤訊息，
應該在**自己的** pytest 就看到「前端會壞」，不是等部署上去才發現。

實際跑的是 tests/fixtures/fake_backend.js：把 api.js 用 node 載入，fetch 換成假後端。
假後端的 501 訊息直接用 app/toolkit/errors.py 產生，跟真的後端同一句。
"""

import json
import os
import shutil
import subprocess

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost/test")
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production-at-least-32-bytes-long")

import pytest  # noqa: E402

from app.ownership import owner_of  # noqa: E402
from app.toolkit import errors  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))


@pytest.fixture(scope="module")
def run():
    if not shutil.which("node"):
        pytest.skip("這台機器沒有 node")
    owner = owner_of("POST", "/api/categories")
    detail = errors.not_implemented("POST /api/categories", owner.label).detail
    out = subprocess.run(["node", os.path.join(HERE, "fixtures", "fake_backend.js"), REPO, detail],
                         capture_output=True, check=True)
    return json.loads(out.stdout.decode("utf-8"))


def test_走的是_http_模式(run):
    assert run["mode"] == "http"


def test_後端只給原始數字_淨額_儲蓄率_存款狀態由前端算(run):
    s = run["summary"]
    assert s["net"] == 8000 and s["rate"] == 0.16
    assert s["level"] == "over" and s["left"] == -2000          # 可支配 40000、花了 42000
    assert s["catName"] == "餐飲"


def test_後端只給_id_名字由前端從分類與家庭成員補上(run):
    assert run["tx"] == {"catName": "餐飲", "userName": "王小明"}
    assert run["budget"] == {"pct": 1.05, "over": True, "catName": "餐飲"}


def test_解析_建議_登入裝置在後端還沒做的時候由前端頂著(run):
    assert run["nlpFallback"] == {"fallback": True, "amounts": [55, 1200]}
    assert run["adviceFallback"]["fallback"] is True and run["adviceFallback"]["count"] > 0
    assert run["sessionsFallback"] == {"fallback": True, "count": 1}


def test_模型服務叫不動_503_也由前端頂著(run):
    assert run["modelDown"]["fallback"] is True and run["modelDown"]["amount"] == 120, run["modelDown"]


def test_沒有備援的_501_講出是哪一支_哪條路由_誰負責_而且不重複(run):
    e = run["notReady"]
    owner = owner_of("POST", "/api/categories").label
    assert e["kind"] == "backend" and e["fn"] == "API.createCategory"
    assert e["route"] == "POST /api/categories" and e["owner"] == owner
    assert e["error"].count("後端還沒做這一支") == 1
    assert e["error"] == "後端還沒做這一支｜出錯的函式：API.createCategory（POST /api/categories，%s）" % owner


def test_形狀不對_伺服器錯誤_連不上_各自有自己的說法(run):
    assert run["shape"]["kind"] == "shape" and "回應少了 alerts" in run["shape"]["error"]
    assert run["server"]["kind"] == "backend" and "HTTP 500" in run["server"]["error"]
    assert run["network"]["kind"] == "network" and run["network"]["error"].startswith("連不上後端")
    for key in ("shape", "server", "network"):
        assert "｜出錯的函式：API." in run[key]["error"]


def test_業務錯誤照後端的原話_不加技術資訊(run):
    b = run["business"]
    assert b["kind"] == "business" and b["error"] == "你已經在一個家庭裡了"


# ===========================================================================
# 前端真的會送出去的請求，後端都收得下
# ===========================================================================
@pytest.fixture(scope="module")
def sent():
    """用 mock 把每一支 API 走過一次，記下 http 轉接器同一組參數會送出的請求。"""
    if not shutil.which("node"):
        pytest.skip("這台機器沒有 node")
    out = subprocess.run(["node", os.path.join(HERE, "fixtures", "record_requests.js"), REPO],
                         capture_output=True, check=True)
    return json.loads(out.stdout.decode("utf-8"))


def _routes():
    from app.main import app

    table = {}
    for r in app.routes:
        if not getattr(r, "path", "").startswith("/api"):
            continue
        for v in (getattr(r, "methods", None) or set()) - {"HEAD", "OPTIONS"}:
            table[(v, r.path)] = r
    return table


def test_前端每一支都走過_而且打的網址就是登記的那條路由(sent):
    import re

    from app.ownership import MEMBERS

    declared = {(v, p) for m in MEMBERS for v, p in m.routes}
    walked = set()
    wrong = []
    for key, rows in sent.items():
        v, p = key.split(" ", 1)
        pat = "^" + re.sub(r"\\{[^}]+\\}", "[^/]+", re.escape(p)) + "$"
        for row in rows:
            req = row["request"]
            if not req or req["method"] != v or not re.match(pat, req["url"].split("?")[0]):
                wrong.append("API.%s → %s（登記的是 %s）" % (row["fn"], req and req["method"] + " " + req["url"], key))
        walked.add((v, p))
    assert not wrong, wrong
    # refresh 是 req() 自己打的，沒有對應的畫面函式
    assert declared - walked == {("POST", "/api/auth/refresh")}, sorted(declared - walked)


def test_前端送的主體與查詢參數_後端的模型都收得下(sent):
    """前端改了欄位名字、或後端改了請求模型，這裡就紅燈——不用等接上才發現 422。"""
    import inspect

    from pydantic import BaseModel, ValidationError

    routes = _routes()
    problems = []
    for key, rows in sent.items():
        v, p = key.split(" ", 1)
        dep = routes[(v, p)].dependant
        queries = {q.alias or q.name for q in dep.query_params}
        for row in rows:
            req = row["request"]
            for part in filter(None, req["url"].partition("?")[2].split("&")):
                if part.split("=")[0] not in queries:
                    problems.append("%s 送了 ?%s，後端沒有宣告" % (key, part.split("=")[0]))
            body = req.get("body")
            params = list(dep.body_params)
            if body is None:
                if any(b.field_info.is_required() for b in params):
                    problems.append("%s 前端沒送主體，後端規定要有" % key)
                continue
            if not params:
                problems.append("%s 前端送了主體，後端沒有收" % key)
                continue
            model = params[0].field_info.annotation
            if not (inspect.isclass(model) and issubclass(model, BaseModel)):
                continue
            try:
                model.model_validate(body)
            except ValidationError as exc:
                problems.append("%s（API.%s）過不了 %s：%s" % (key, row["fn"], model.__name__, exc.errors()[0]))
            if model.model_config.get("extra") == "forbid" and set(body) - set(model.model_fields):
                problems.append("%s 多送了 %s，%s 不收多的欄位" % (key, sorted(set(body) - set(model.model_fields)), model.__name__))
    assert not problems, "\n".join(problems)


def test_每一支的路徑參數都有宣告_文件頁試打得了():
    """路徑寫了 {aid}，函式或守衛卻沒宣告的話，/docs 上不會出現那一格，試打時填不了。"""
    import re

    from fastapi.dependencies.utils import get_flat_dependant

    missing = []
    for (v, p), r in _routes().items():
        want = set(re.findall(r"\{(\w+)\}", p))
        got = {x.name for x in get_flat_dependant(r.dependant).path_params}
        if want != got:
            missing.append("%s %s：路徑有 %s，宣告了 %s" % (v, p, sorted(want), sorted(got)))
    assert not missing, missing
