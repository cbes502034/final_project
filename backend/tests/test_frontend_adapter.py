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
