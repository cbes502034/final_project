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

import glob
import io
import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def read(rel: str) -> str:
    return io.open(os.path.join(REPO, rel), encoding="utf-8").read()


def _cn(n: int) -> str:
    """把數字寫成中文：11 → 十一。手冊內文用中文數字，測試要能比對。"""
    d = "零一二三四五六七八九"
    if n < 10:
        return d[n]
    if n < 20:
        return "十" + (d[n - 10] if n > 10 else "")
    return d[n // 10] + "十" + (d[n % 10] if n % 10 else "")


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
        "app/toolkit/images.py",
        "app/toolkit/alerts.py",
        "app/toolkit/scope.py",
    ]
    missing = [f for f in expected
               if not os.path.exists(os.path.join(REPO, "backend", f))]
    assert not missing, "工具箱少了這些檔案：" + "、".join(missing)


def test_每個工具都要寫在索引裡():
    """toolkit/__init__.py 的那張表要列出每一個模組。

    這份索引就是成員找工具的入口。漏掉一個，那個工具等於不存在——
    images 就這樣被漏了很久：檔案在、測試也過，但沒人知道它存在。
    所以改成讓測試去數資料夾，不要靠人維護清單。
    """
    index = read("backend/app/toolkit/__init__.py")
    names = sorted(
        os.path.basename(p)[:-3]
        for p in glob.glob(os.path.join(REPO, "backend", "app", "toolkit", "*.py"))
        if not os.path.basename(p).startswith("__")
    )
    undocumented = [n for n in names if ("    %s " % n) not in index]
    assert not undocumented, (
        "這些工具沒有寫進 __init__.py 的索引：" + "、".join(undocumented)
    )


def test_工具箱沒有留下未完成的東西():
    """
    ⚠️ **工具箱裡不可以有 TODO 或 NotImplementedError。**

    它的定位是「完整可用的工具」，不是填空題。
    留下 TODO 的話，成員 import 進來用到一半才發現是空的，
    那比一開始就沒有這個工具還糟。
    """

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
    frontend/js/api.js 的 http 轉接器打的每一支路由，後端都必須有。

    這是「資訊沒對接上」最常見的形式：前端寫了一支後端從來沒做的 API，
    等到接上去才發現 404。
    """
    from app.ownership import all_routes

    js = read("frontend/js/api.js")
    called = set(re.findall(r"req\('(/api/[^']*)'", js))
    # 帶路徑參數的寫法是 '/api/transactions/' + id
    called = {c.rstrip("/") for c in called}

    backend_paths = {p.split("{")[0].rstrip("/") for _, p in all_routes()}

    orphans = sorted(c for c in called if c not in backend_paths)
    assert not orphans, "前端會打、但後端沒有的路由：" + "、".join(orphans)


def test_畫面數在程式與手冊之間一致():
    """app.js 的 ROUTES 有幾個畫面，手冊就要寫幾個。

    這種數字最會飄：加一個畫面，程式改了、文件沒改，
    報告上就留著一個不存在的數字。讓測試去數，人不要數。
    """
    app = read("frontend/js/app.js")
    m = re.search(r"var ROUTES = \{(.*?)\};", app, re.S)
    assert m, "app.js 裡找不到 ROUTES"
    n = len(re.findall(r"[\w']+\s*:", m.group(1)))

    handbook = read("frontend/docs/index.html")
    assert "%d SCREENS" % n in handbook, \
        "手冊角標的畫面數對不上，app.js 有 %d 個" % n

    assert "%s個畫面" % _cn(n) in handbook, \
        "手冊內文沒寫「%s個畫面」" % _cn(n)


def test_前端有登入畫面而且不再說自己沒有():
    """契約文件曾經寫著「前端目前還沒有」登入畫面。做好了就不能再這樣寫。"""
    app = read("frontend/js/app.js")
    for f in ("vLogin", "vRegister", "vProfile"):
        assert "function %s(" % f in app, "app.js 少了 %s" % f

    api = read("frontend/js/api.js")
    for fn in ("login:", "register:", "logout:", "uploadAvatar:", "authState:"):
        assert api.count(fn) >= 3, \
            "%s 要在 mock、http、facade 三層都有，現在只有 %d 個" % (fn, api.count(fn))

    contract = read("docs/02-前後端串接契約.md")
    for stale in ("前端目前還沒有", "前端現在沒有登入畫面"):
        assert stale not in contract, "契約還寫著「%s」，但已經做好了" % stale


def test_心智圖的路由數也要對():
    """手冊底部的心智圖用另一種寫法標路由數（api: '8 支'），
    上面那條測試的正規表達式抓不到它——所以它真的飄掉過。
    """
    from app.ownership import MEMBERS

    handbook = read("frontend/docs/index.html")
    for m in MEMBERS:
        want = "{ dom: '%s'" % m.domain
        i = handbook.find(want)
        assert i >= 0, "心智圖裡找不到 %s" % m.domain
        node = handbook[i:i + 200]
        mo = re.search(r"api: '(\d+) 支'", node)
        assert mo, "%s 的節點沒寫路由數" % m.domain
        assert int(mo.group(1)) == len(m.routes), \
            "心智圖說 %s 有 %s 支，ownership.py 說 %d 支" % (
                m.domain, mo.group(1), len(m.routes))


def test_資料表張數在三份文件裡一致():
    """手冊的資料庫那節列了幾張表，其他地方就要寫幾張。

    這一項真的走散過，而且是三種數字：
    規格文件寫 12 張、手冊內文寫 13 張、手冊角標寫 14 TABLES。
    原因是加了 notifications 之後只改了角標。所以改成用數的。
    """
    handbook = read("frontend/docs/index.html")
    spec = read("docs/01-tech-stack-and-api.md")

    tables = re.findall(r'acc__code">([a-z_]+)</code>', handbook)
    n = len(tables)
    assert n >= 10, "資料庫那節只抓到 %d 張表，選擇器大概壞了" % n
    assert "notifications" in tables, "監管通知要有自己的資料表"

    assert "%d TABLES" % n in handbook, "手冊角標的表數不是 %d" % n
    assert "%d 張表" % n in handbook, "手冊內文沒寫「%d 張表」" % n
    assert "%d 張表" % n in spec, "規格文件沒寫「%d 張表」" % n

    # 舊的數字不可以還留著
    for stale in range(10, n):
        assert "%d 張表" % stale not in handbook, "手冊還留著「%d 張表」" % stale
        assert "%d 張表" % stale not in spec, "規格文件還留著「%d 張表」" % stale


def test_不可實作的路由在任何一端都不存在():
    """NEVER_IMPLEMENT 列的路由，前端不可以打、後端不可以做。

    這一條擋的是 POST /api/auth/switch——管理者登入子女帳號。
    它曾經以「示範模式的切換身分鈕」存在於前端，已經拿掉了。
    功能被拿掉之後最容易發生的事，是過幾週有人覺得方便又加回來，
    所以用測試把它釘死。
    """
    from app.ownership import NEVER_IMPLEMENT, all_routes

    backend = {"%s %s" % (v, p) for v, p in all_routes()}
    api_js = read("frontend/js/api.js")
    app_js = read("frontend/js/app.js")

    for route, why in NEVER_IMPLEMENT:
        assert route not in backend, "後端實作了不該實作的 %s\n%s" % (route, why)

        path = route.split(" ", 1)[1]
        assert path not in api_js, "前端的 api.js 還在打 %s\n%s" % (path, why)
        assert path not in app_js, "前端的 app.js 還在打 %s\n%s" % (path, why)


def test_切換身分已經從前端絕跡():
    """有了真的登入登出，「切換身分」就是一顆後門形狀的按鈕。"""
    for rel in ("frontend/js/api.js", "frontend/js/app.js", "frontend/index.html"):
        src = read(rel)
        for bad in ("switchUser", "data-switch", "切換身分"):
            assert bad not in src, "%s 還留著「%s」" % (rel, bad)

    # 文件也不可以還把它講成「前端專用、之後要拿掉」——已經拿掉了
    for rel in ("README.md", "backend/README.md", "docs/02-前後端串接契約.md"):
        src = read(rel)
        assert "前端專用、後端不實作" not in src, "%s 的說法過時了" % rel
        assert "示範模式專用" not in src, "%s 的說法過時了" % rel


def test_規格文件的分工總表也要對():
    """docs/01 的分工總表用第三種寫法標路由數（`| 8 支 |`）。

    前兩條測試數的是路由明細表的列數，抓不到這張總表——
    所以它也飄掉過：成員1 停在 8 支（實際 11）、成員4 停在 9 支（實際 12）。
    """
    from app.ownership import MEMBERS

    spec = read("docs/01-tech-stack-and-api.md")
    for m in MEMBERS:
        mo = re.search(
            r"\| \*\*%s\*\* \| \*\*%s\*\* \| `%s` \| (\d+) 支 \|"
            % (re.escape(m.label), re.escape(m.domain), re.escape(m.branch)),
            spec)
        assert mo, "分工總表裡找不到 %s" % m.label
        assert int(mo.group(1)) == len(m.routes), \
            "分工總表說 %s 有 %s 支，ownership.py 說 %d 支" % (
                m.label, mo.group(1), len(m.routes))


def test_可見範圍不可以用角色判斷():
    """可見範圍只能由 guardianships 決定。

    寫成 `if role == 'master': return everyone` 的話，
    被監管的人就無法確認自己的紀錄被誰看過——「誰看得到我」
    必須是一份可以查、可以列出來的清單。
    """
    api = read("frontend/js/api.js")
    mo = re.search(r"function visibleUsers\(meId\) \{(.*?)\n  \}", api, re.S)
    assert mo, "api.js 裡找不到 visibleUsers"
    body = mo.group(1)
    assert "role" not in body, \
        "visibleUsers 又用角色判斷了：\n" + body
    assert "guardianships" in body, "visibleUsers 沒有看 guardianships"


def test_檔案系統說明書要跟得上實際的檔案():
    """toolkit/ 多一個檔案，說明書就要多一列。

    說明書是別人找工具的入口，落後一版等於那個工具不存在。
    所以不靠人記得去改，讓測試去比對資料夾。
    """
    doc = read("frontend/docs/files.html")
    names = sorted(
        os.path.basename(p)
        for p in glob.glob(os.path.join(REPO, "backend", "app", "toolkit", "*.py"))
        if not os.path.basename(p).startswith("__")
    )
    missing = [n for n in names
               if '<span class="fname">%s</span>' % n not in doc]
    assert not missing, (
        "檔案系統說明書的工具箱表格少了：" + "、".join(missing)
    )


def test_手冊的資料表區塊要跟_data_js_一致():
    """手冊那一大段資料表是從 frontend/js/data.js 的 schema 生出來的。

    這兩邊本來是各寫各的，所以加了 notifications 只改到一邊。
    現在改成生成，這條測試確保沒有人再手改 HTML 讓它們分岔。
    """
    data = read("frontend/js/data.js")
    handbook = read("frontend/docs/index.html")

    in_data = re.findall(r"\{ t: '([a-z_]+)'", data)
    in_doc = re.findall(r'acc__code">([a-z_]+)</code>', handbook)

    assert in_data, "data.js 裡找不到 schema"
    assert in_data == in_doc, (
        "手冊的資料表跟 data.js 對不上。"
        "　data.js：%s　／　手冊：%s" % ("、".join(in_data), "、".join(in_doc))
    )


def test_群組與提醒的前端三層都有():
    """新功能的 mock、http、facade 三層簽名要一致，缺一層就會在切換時壞掉。"""
    api = read("frontend/js/api.js")
    for fn in ("groups:", "createGroup:", "archiveGroup:",
               "alerts:", "createAlert:", "deleteAlert:", "savingsGoals:"):
        assert api.count(fn) >= 3,             "%s 要在 mock、http、facade 三層都有，現在只有 %d 個" % (fn, api.count(fn))

    app = read("frontend/js/app.js")
    assert "function vGroups(" in app, "app.js 少了群組頁"
    assert "function paintAlerts(" in app, "app.js 少了提醒設定"


def test_權限矩陣要跟_data_js_一致():
    """手冊的權限矩陣是從 frontend/js/data.js 的 permissions 生出來的。

    這兩份本來各寫各的，而且已經各自長出對方沒有的列——
    手冊有「收到子女新增紀錄的通知」，data.js 沒有；
    data.js 有「查看沒有指派給自己的人」，手冊沒有。
    """
    data = read("frontend/js/data.js")
    handbook = read("frontend/docs/index.html")

    actions = re.findall(r"\{ action: '([^']+)'", data)
    assert actions, "data.js 裡找不到 permissions"

    missing = [a for a in actions
               if ("<td>%s</td>" % a) not in handbook
               and ("<td><b>%s</b></td>" % a) not in handbook]
    assert not missing, "手冊的權限矩陣少了：" + "、".join(missing)

    # 建立群組不分角色，這是刻意的設計，不可以被悄悄改掉
    assert "{ action: '建立群組（帳本）', master: 'Y', parent: 'Y', member: 'Y' }" in data,         "建立群組應該三個角色都可以——記帳的分類方式不該由家裡的階級決定"
