"""每一支路由的說明字串，格式要一致。

===========================================================================
為什麼要測「說明的格式」
===========================================================================
說明字串是四個人動手寫程式時唯一會讀的東西。它少一段、或是【完整寫法】裡的程式
貼上去跑不起來，那一支就沒人做得完——而這種事不會有任何錯誤訊息，只會卡住一個人一個下午。

所以這裡把格式釘死：
    · 十一個段落一個都不能少，而且順序固定
    · 【完整寫法】的程式要真的能解析、函式名字與路由要對得上、不能留著 @stub
    · 同一個檔案裡每一支的「第一步（import）」要一模一樣（不然照做會互相覆蓋）

「程式真的跑得起來嗎」由 tests/routes/ 其他檔案的 [說明] 那一輪負責。
"""

import ast
import inspect

import pytest

from app import routers
from tests.routes.conftest import apply, parse_doc

SECTIONS = [
    "【這支做什麼】", "【前端怎麼打】", "【誰能打】", "【成功回應】", "【錯誤回應】",
    "【會用到的資料表】", "【每一步用的工具與資料庫方法】", "【寫法步驟】", "【完整寫法】", "【做完怎麼確認】",
]
REQUEST_SECTIONS = ("【請求主體】", "【查詢參數】", "【路徑參數】", "【請求參數】")


def _routes():
    out = []
    for module in routers.ALL:
        for route in module.router.routes:
            for method in sorted(route.methods):
                out.append(pytest.param(module, method, route, id="%s %s" % (method, route.path)))
    return out


ROUTES = _routes()


@pytest.mark.parametrize("module, method, route", ROUTES)
def test_說明字串有十一個段落而且順序固定(module, method, route):
    doc = inspect.getdoc(route.endpoint) or ""
    assert doc, "%s %s 沒有說明字串" % (method, route.path)
    lines = doc.splitlines()
    assert lines[0] == route.summary, "說明的第一行要跟 summary 一樣"
    assert lines[2] == "%s /api%s" % (method, route.path), "第三行要是「方法 路徑」"
    assert any(s in doc for s in REQUEST_SECTIONS), "要有【請求主體】【查詢參數】【路徑參數】【請求參數】其中一段"
    at = -1
    for section in SECTIONS:
        i = doc.find(section)
        assert i > 0, "少了 %s" % section
        assert i > at, "%s 的位置不對（段落順序是固定的）" % section
        at = i


@pytest.mark.parametrize("module, method, route", ROUTES)
def test_完整寫法的程式解析得動而且對得上這一支(module, method, route):
    doc = inspect.getdoc(route.endpoint) or ""
    parsed = parse_doc(doc)
    assert parsed, "%s %s 的說明少了【完整寫法】" % (method, route.path)
    tree = ast.parse(parsed["code"])
    fn = tree.body[-1]
    assert isinstance(fn, ast.FunctionDef), "第二步的最後要是一個函式"
    assert fn.name == route.endpoint.__name__, "函式名字要跟這一支一樣"
    decorators = [ast.unparse(d) for d in fn.decorator_list]
    assert any(d.startswith("router.%s(%r" % (method.lower(), route.path)) for d in decorators), \
        "第一個裝飾器要是 @router.%s(%r, …)：%s" % (method.lower(), route.path, decorators)
    assert "stub" not in decorators, "第二步不要留著 @stub"
    assert "not_ready" not in parsed["code"], "第二步不要留著 raise not_ready"
    assert "import " not in parsed["imports"].split("from")[0] or parsed["imports"], "第一步要是 import 區"
    ast.parse(parsed["imports"])
    for path, func, code in parsed["extra"]:
        assert path.startswith("app/") and path.endswith(".py"), path
        extra = ast.parse(code).body[-1]
        assert isinstance(extra, ast.FunctionDef) and extra.name == func, "第三步要是 %s()" % func


@pytest.mark.parametrize("module", routers.ALL, ids=lambda m: m.__name__.rsplit(".", 1)[-1])
def test_同一個檔案裡每一支的第一步都一樣(module):
    """apply() 會在不一樣的時候丟 AssertionError——照做的人才不會被互相覆蓋的 import 卡住。"""
    source, _extra = apply(open(module.__file__, encoding="utf-8").read())
    ast.parse(source)                      # 十幾支一起套上去，整個檔案還是合法的 Python
