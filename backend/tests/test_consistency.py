"""
跨檔案一致性檢查：確保分工資訊沒有在任何一個地方走散。

===========================================================================
為什麼需要這個？
===========================================================================
「誰負責哪些路由」這件事寫在六個地方：

    backend/app/ownership.py        ← 單一事實來源
    backend/app/*/*.py              各檔案的檔頭
    backend/README.md
    README.md
    docs/01-tech-stack-and-api.md
    frontend/docs/index.html        專題手冊
    frontend/docs/api.html          API 瀏覽頁

靠人記得同時更新六個地方是不可能的。所以**用測試把它們綁在一起**：
任何一個地方走散，跑 pytest 就會紅燈。

這幾支測試不檢查文字內容（那會太脆弱），只檢查**結構性的事實**：
路由數對不對、歸屬對不對、有沒有引用到不存在的檔案。
"""

import io
import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def read(rel: str) -> str:
    return io.open(os.path.join(REPO, rel), encoding="utf-8").read()


def test_每位成員的路由數在四份文件裡一致():
    """
    ownership.py 說成員3 有 10 支，那另外三個地方也必須說 10 支。

    這是最容易走散的一項：有人搬動了一支路由，改了程式卻忘了改文件。
    """
    from app.ownership import MEMBERS

    api_html = read("frontend/docs/api.html")
    handbook = read("frontend/docs/index.html")
    spec = read("docs/01-tech-stack-and-api.md")

    for m in MEMBERS:
        n = len(m.routes)

        # API 瀏覽頁：每支路由標著 o: 'm3'
        got = len(re.findall(r"o: '%s'" % m.key, api_html))
        assert got == n, f"API 瀏覽頁的 {m.label} 有 {got} 支，ownership.py 說 {n} 支"

        # 手冊的卡片：「數字與建議 · 10 支」
        assert f"{m.domain} · {n} 支" in handbook, \
            f"手冊沒有寫「{m.domain} · {n} 支」"

        # 規格文件的 API 目錄：負責人欄
        got = len(re.findall(r"\| %s(?: ★)? \|" % m.label, spec))
        assert got == n, f"規格文件的 {m.label} 有 {got} 列，ownership.py 說 {n} 支"


def test_分支名稱到處都一樣():
    """分支名稱錯了，組員會 checkout 到不存在的分支。"""
    from app.ownership import MEMBERS

    for src in ("frontend/docs/api.html", "frontend/docs/index.html",
                "README.md", "backend/README.md", "docs/01-tech-stack-and-api.md"):
        text = read(src)
        for m in MEMBERS:
            assert m.branch in text, f"{src} 裡找不到分支名稱 {m.branch}"


def test_工具箱的檔案都在():
    """
    toolkit/ 底下的東西是**已經寫好交付的**，少一個就代表交付不完整。

    成員自己要建的檔案（routers/、models/…）不在這裡檢查——
    那些還沒建是正常的，屬於進度不是錯誤。
    """
    expected = [
        "app/toolkit/__init__.py",
        "app/toolkit/config.py",
        "app/toolkit/db.py",
        "app/toolkit/passwords.py",
        "app/toolkit/tokens.py",
        "app/toolkit/deps.py",
        "app/toolkit/errors.py",
        "app/toolkit/period.py",
        "app/toolkit/money.py",
    ]
    missing = [f for f in expected
               if not os.path.exists(os.path.join(REPO, "backend", f))]
    assert not missing, "工具箱少了這些檔案：" + "、".join(missing)


def test_工具箱沒有留下未完成的東西():
    """
    ⚠️ **工具箱裡不可以有 TODO 或 NotImplementedError。**

    它的定位是「完整可用的工具」，不是填空題。
    留下 TODO 的話，成員 import 進來用到一半才發現是空的，
    那比一開始就沒有這個工具還糟。
    """
    import glob

    bad = []
    for path in glob.glob(os.path.join(REPO, "backend", "app", "toolkit", "*.py")):
        text = io.open(path, encoding="utf-8").read()
        name = os.path.basename(path)
        # 說明文字裡提到 TODO 是可以的，實際的標記不行
        if "TODO(" in text:
            bad.append(f"{name} 有 TODO 標記")
        if "NotImplementedError" in text:
            bad.append(f"{name} 有 NotImplementedError")
    assert not bad, "工具箱不該有未完成的東西：" + "、".join(bad)


def test_已建立的檔案都標了負責人():
    """
    分工表裡列到、而且**已經建立**的檔案，檔頭要寫負責人。

    還沒建立的跳過——那是進度。
    """
    from app.ownership import MEMBERS

    owned = set()
    for m in MEMBERS:
        owned.update(m.files)
        owned.update(m.shared)

    missing = []
    for f in sorted(owned):
        p = os.path.join(REPO, "backend", f)
        if not os.path.exists(p):
            continue
        if "負責人" not in io.open(p, encoding="utf-8").read()[:600]:
            missing.append(f)

    assert not missing, "檔頭沒有標負責人的檔案：" + "、".join(missing)


def test_前端沒有呼叫不存在的後端路由():
    """
    frontend/js/api.js 的 http 轉接器打的每一支路由，
    後端都必須有（或明確列在 FRONTEND_ONLY 裡）。

    這是「資訊沒對接上」最常見的形式：前端寫了一支後端從來沒做的 API，
    等到接上去才發現 404。
    """
    from app.ownership import FRONTEND_ONLY, all_routes

    js = read("frontend/js/api.js")
    called = set(re.findall(r"req\('(/api/[^']*)'", js))
    # 帶路徑參數的寫法是 '/api/transactions/' + id
    called = {c.rstrip("/") for c in called}

    backend_paths = {p.split("{")[0].rstrip("/") for _, p in all_routes()}
    allowed = {a.split(" ", 1)[1].rstrip("/") for a, _ in FRONTEND_ONLY}

    orphans = sorted(c for c in called if c not in backend_paths and c not in allowed)
    assert not orphans, (
        "前端會打、但後端沒有也沒列在 FRONTEND_ONLY 的路由：" + "、".join(orphans)
    )
