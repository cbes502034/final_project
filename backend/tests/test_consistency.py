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
    assert "{ action: '建立群組（帳本）', parent: 'Y', child: 'Y' }" in data, \
        "建立群組應該兩種角色都可以——記帳的分類方式不該由家裡的階級決定"


def test_每一條建立紀錄的路徑都要帶群組():
    """新記的一筆沒有 group，就會被群組篩選擋掉——記了卻找不到。

    這是真的發生過的：加了群組之後，createTransaction、nlpConfirm、
    nlpConfirmBatch 三條路徑都沒補上 group，於是記帳功能整個失效，
    畫面上卻沒有任何錯誤訊息。

    所以規定：**每一條建立路徑都要走 groupFor()**，不要各自寫。
    """
    api = read("frontend/js/api.js")
    assert "function groupFor(" in api, "api.js 少了 groupFor()"

    for fn in ("createTransaction: function", "nlpConfirm: function",
               "nlpConfirmBatch: function"):
        i = api.index(fn)
        body = api[i:i + 1400]
        assert "groupFor(" in body, "%s 沒有走 groupFor()，新紀錄會沒有群組" % fn


def test_問號不可以放在按鈕裡面():
    """helpBtn() 回傳的是 <button>，放進另一個 <button> 會被瀏覽器拆開。

    這真的發生過：記帳頁的模式切換鈕裡放了問號，
    解析器在內層按鈕的位置把外層關掉，後面的箭頭 SVG 被踢出按鈕，
    CSS 對不上就用原始尺寸畫出來——畫面上出現一個 1162px 的巨大箭頭。

    而且它不會報錯，只會變得很醜。
    """
    app = read("frontend/js/app.js")
    for mo in re.finditer(r"helpBtn\(", app):
        # 往前找最近的標籤開頭，確認不是 <button
        before = app[max(0, mo.start() - 400):mo.start()]
        opens = before.count("<button")
        closes = before.count("</button>")
        assert opens <= closes, (
            "第 %d 個字元附近的 helpBtn() 被包在 <button> 裡面了" % mo.start()
        )


# ===========================================================================
# 前端：呼叫了一個不存在的函式
# ===========================================================================
#
# 這一類壞法最難發現：檔案語法完全正確，node --check 也過，
# 畫面照常長出來——直到使用者剛好點到那一行，才在主控台丟 ReferenceError。
#
# 實際踩過：抽屜改成推開內容之後，量測高度的 measureTop() 被拿掉了，
# 但 pushForDrawer() 裡還留著一行呼叫。每捲一次、每開一次抽屜就噴一次，
# 累積 131 個錯誤，而畫面上完全看不出來。
#
# 下面這支用很土的方法解決：把字串、註解、正則塗掉，
# 收集所有宣告過的名字，再去找呼叫得出來卻沒宣告的。

_BROWSER = set(
    """
    if for while switch catch return typeof new delete void instanceof in of do
    else try finally function var let const throw case break continue yield await
    Array Object String Number Boolean Date Math JSON RegExp Error Promise Set Map
    parseInt parseFloat isNaN isFinite encodeURIComponent decodeURIComponent
    setTimeout setInterval clearTimeout clearInterval requestAnimationFrame
    alert confirm prompt fetch console document window localStorage sessionStorage
    Uint8Array Intl Symbol WeakMap Proxy Reflect BigInt structuredClone
    queueMicrotask getComputedStyle matchMedia CustomEvent Event DOMParser
    MutationObserver IntersectionObserver ResizeObserver AbortController
    FileReader Image Audio Blob File FormData URL URLSearchParams Headers
    Request Response XMLHttpRequest WebSocket EventSource Notification
    TextEncoder TextDecoder Worker
    """.split()
)

# 正則後面可以接的旗標；判斷「這個 / 是正則還是除號」用前一個字元
_BEFORE_RE = set("(,=:[!&|?{};\n+-*%~^<>")


def _blank(src):
    """把字串、樣板、正則、註解換成等長的空白，行號才對得起來。

    ⚠️ 正則一定要處理。像 /^[^']*$/ 裡的單引號如果被當成字串開頭，
    從那一行開始所有引號配對就全錯，後面會冒出一整串假警報。
    """
    out, i, n, prev = [], 0, len(src), ""
    while i < n:
        c, two = src[i], src[i:i + 2]
        if c == "/" and two not in ("//", "/*") and (prev == "" or prev in _BEFORE_RE):
            j, in_class = i + 1, False
            while j < n:
                if src[j] == "\\":
                    j += 2
                    continue
                if src[j] == "[":
                    in_class = True
                elif src[j] == "]":
                    in_class = False
                elif src[j] == "/" and not in_class:
                    break
                elif src[j] == "\n":
                    break
                j += 1
            if j < n and src[j] == "/":
                j += 1
                while j < n and src[j] in "gimsuy":
                    j += 1
                out.append(" " * (j - i))
                prev, i = "/", j
                continue
        if two == "//":
            j = src.find("\n", i)
            j = n if j < 0 else j
            out.append(" " * (j - i))
            i = j
        elif two == "/*":
            j = src.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append("".join(ch if ch == "\n" else " " for ch in src[i:j]))
            i = j
        elif c in "\"'`":
            j = i + 1
            while j < n and src[j] != c:
                if src[j] == "\\":
                    j += 1
                j += 1
            j = min(j + 1, n)
            out.append("".join(ch if ch == "\n" else " " for ch in src[i:j]))
            i = j
        else:
            out.append(c)
            if not c.isspace():
                prev = c
            i += 1
    return "".join(out)


def _declared(code):
    names = set()
    for pat in (
        r"\bfunction\s+([A-Za-z_$][\w$]*)",
        r"\b(?:var|let|const)\s+([A-Za-z_$][\w$]*)",
        r",\s*([A-Za-z_$][\w$]*)\s*=",
        r"\bcatch\s*\(\s*([A-Za-z_$][\w$]*)",
    ):
        names |= set(re.findall(pat, code))
    for mo in re.finditer(r"\bfunction\s*[A-Za-z_$\w]*\s*\(([^)]*)\)", code):
        for p in mo.group(1).split(","):
            p = p.strip()
            if re.match(r"^[A-Za-z_$][\w$]*$", p):
                names.add(p)
    return names


def test_前端沒有呼叫不存在的函式():
    """語法對、檔案載得進來，但按下去就 ReferenceError 的那一類。"""
    problems = []
    for path in (
        "frontend/js/app.js",
        "frontend/js/api.js",
        "frontend/js/notify.js",
        "frontend/js/data.js",
        "frontend/js/stars.js",
    ):
        code = _blank(read(path))
        known = _declared(code) | _BROWSER
        for mo in re.finditer(r"(?<![.\w$])([a-zA-Z_$][\w$]*)\s*\(", code):
            if mo.group(1) in known:
                continue
            line = code.count("\n", 0, mo.start()) + 1
            problems.append("%s:%d 呼叫了沒有宣告的 %s()" % (path, line, mo.group(1)))

    assert not problems, "\n".join(problems)


def test_家庭角色只有兩層():
    """master 不是家庭角色。

    早期版本把「家裡權限最高的人」也叫 master，於是一個家庭有三種角色。
    但 master 現在是**平台管理員**——系統層級，不屬於任何家庭。
    混在一起的話，任何一個家長都會變成能停權別人家使用者的人。
    """
    data = read("frontend/js/data.js")

    roles = re.findall(r"\{ id: '(\w+)', name: '([^']+)', layer: '([^']+)'", data)
    assert roles, "data.js 裡找不到 roles"
    layers = {r[0]: r[2] for r in roles}
    assert layers.get("master") == "平台", "master 必須是平台層級"
    assert layers.get("parent") == "家庭"
    assert layers.get("child") == "家庭"

    # 沒有人的 role 還掛著 master
    assert "role: 'master'" not in data, \
        "還有成員掛著 role: 'master'——master 不是家庭角色"
    assert "role: 'member'" not in data, \
        "member 已經改名為 child，還有地方沒改"


def test_平台管理員不可以讀任何人的財務資料():
    """停權是關門，不是配鑰匙。

    這跟「管理人員不可以進入子女的帳號」是同一條原則。
    一個能讀全系統消費明細的帳號，比家長越權嚴重得多——
    家長至少還在 guardianships 表上留下痕跡、被監管的人看得到；
    平台管理員如果能看，那是一個沒有人看得見的視角。
    """
    data = read("frontend/js/data.js")
    must_be_no = [
        "查看任何人的收支明細",
        "修改任何人的資料",
        "登入他人帳號",
    ]
    for action in must_be_no:
        assert "{ action: '%s', master: 'N' }" % action in data, \
            "平台權限表裡「%s」必須是 N" % action

    # 後端工具也要擋
    roles_py = read("backend/app/toolkit/roles.py")
    mo = re.search(r"PLATFORM_ACTIONS[^=]*=\s*frozenset\(\s*\{([^}]*)\}", roles_py)
    assert mo, "roles.py 裡找不到 PLATFORM_ACTIONS"
    allowed = mo.group(1)
    for bad in ("transaction", "ledger", "read_user", "impersonate"):
        assert bad not in allowed, \
            "PLATFORM_ACTIONS 混進了會碰到財務資料的動作：" + bad


def test_年齡不可以參與任何權限判斷():
    """系統只提供功能，幾歲該被管是那一家自己的事。

    一旦寫了 `if age < 18`，系統就開始替別人的家庭做價值判斷了。
    而且年齡是會變的——用它當權限依據，權限就會在某個生日當天自己改變。
    """
    for path in ("frontend/js/api.js", "frontend/js/app.js"):
        src = read(path)
        for bad in ("age < 18", "age >= 18", "age<18", "未成年"):
            assert bad not in src, "%s 還在用年齡判斷權限：%s" % (path, bad)


def test_可見範圍是聯集不是交集():
    """監管不可以被帳本切斷。

    早期版本用交集（人 AND 帳本），那讓監管有一個一鍵可繞的破口：
    被監管的人只要另外開一本不加監管者的帳，記在那裡就完全看不到了。
    他甚至不用離開任何群組。

    所以改成聯集：
        A 我或我監管的人記的 —— 跨所有帳本
        B 記在我有加入的帳本裡 —— 那本帳的成員彼此看得到
    """
    api = read("frontend/js/api.js")

    mo = re.search(r"function canSeeRow\(([^)]*)\) \{(.*?)\n  \}", api, re.S)
    assert mo, "api.js 裡找不到 canSeeRow"
    body = mo.group(2)
    assert "||" in body, "canSeeRow 必須是聯集（||），不可以改回 &&"
    assert "&&" not in body, "canSeeRow 出現了 &&，那會變回交集"

    # 明細的篩選必須走 canSeeRow，不可以自己再寫一次兩道判斷
    assert "if (!canSeeRow(t, vis, vgs)) return false;" in api, \
        "listTransactions 沒有走 canSeeRow"

    # 統計只能走 A，不可以把帳本裡別人的錢算進某個人的總額
    mo2 = re.search(r"summary: function \(f\) \{(.*?)\n    \},", api, re.S)
    assert mo2, "api.js 裡找不到 summary"
    assert "canSeeRow" not in mo2.group(1), \
        "統計不可以走聯集——B 會把共用帳本裡別人的錢算進這個人的總額"


def test_通知與明細的可見範圍必須一致():
    """一則點進去卻看不到東西的通知，比沒有通知更糟。

    監管的通知只看監管關係（跨帳本），明細也必須看得到同一批紀錄。
    兩邊用不同規則的話，使用者會收到自己打不開的通知。
    """
    api = read("frontend/js/api.js")
    mo = re.search(r"type: 'ward_transaction'", api)
    assert mo, "找不到 ward_transaction"

    # 產生通知的那段不可以加上帳本篩選
    head = api[max(0, mo.start() - 1200):mo.start()]
    assert "wards.indexOf(t.user) >= 0" in head, \
        "監管通知應該只看監管關係"
    assert "vgs.indexOf(t.group)" not in head, \
        "監管通知不可以再加帳本篩選——那會跟明細對不起來"


def test_手冊的資料表要逐欄跟得上_data_js():
    """表名對得上還不夠，**欄位說明也會走散**。

    實際發生過：data.js 的 users 表加了 is_platform_admin、
    families 把 master_id 換成 created_by，但手冊那一大塊 HTML 是手寫的，
    整整落後一版——上面還寫著 master_id 和「判斷是否未成年」。

    表格數對得上，所以舊測試沒抓到。這支逐欄比對。
    """
    data = read("frontend/js/data.js")
    handbook = read("frontend/docs/index.html")

    block = data[data.index("  schema: ["):data.index("  relations:")]
    # [['欄位名', '型別', '說明'], ...]
    cols = re.findall(r"\['([a-z_]+)', '([A-Z][A-Za-z0-9(),. ]*)', '([^']*)'\]", block)
    assert len(cols) > 80, "解析到的欄位太少：%d" % len(cols)

    missing = []
    for name, typ, note in cols:
        cell = "<td class=\"mono\"><b>%s</b></td>" % name
        if cell not in handbook:
            missing.append("%s（欄位沒出現）" % name)
        elif note and ("<td>%s</td>" % note.replace("&", "&amp;")) not in handbook:
            missing.append("%s 的說明「%s」" % (name, note[:24]))

    assert not missing, (
        "手冊的資料表落後 data.js：" + "、".join(missing[:8])
        + "\n重新產生那一段，不要手改"
    )


# ===========================================================================
# 示範資料的數字必須自洽
# ===========================================================================
#
# 這幾支要用 node 把 data.js 讀進來算。理由是：這些數字錯掉的時候，
# 畫面不會壞、也不會報錯，只會「兩個數字不一樣」——
# 使用者要自己去加總才會發現，那就太遲了。

def _load_data():
    """用 node 把 data.js 讀成 JSON。沒有 node 就跳過。"""
    import json
    import shutil
    import subprocess
    import tempfile

    if not shutil.which("node"):
        import pytest
        pytest.skip("這台機器沒有 node")

    script = (
        "global.window = {};"
        "require(process.argv[2]);"
        "process.stdout.write(JSON.stringify(window.DATA));"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                     encoding="utf-8") as fh:
        fh.write(script)
        tmp = fh.name
    out = subprocess.run(
        ["node", tmp, os.path.join(REPO, "frontend", "js", "data.js")],
        capture_output=True, check=True)
    return json.loads(out.stdout.decode("utf-8"))


def test_明細加總要等於成員彙總():
    """members[] 上的 income/expense，必須等於 transactions 加起來。

    這兩份本來是各寫各的：KPI 讀彙總、圓餅圖讀明細，於是
    「本月支出 41,230」下面那張圖加起來只有 32,770——
    同一個畫面上兩個數字互相打臉，而且沒有任何錯誤訊息。
    """
    D = _load_data()
    per = {}
    for t in D["transactions"]:
        if t["kind"] == "transfer":          # 轉帳不是收支
            continue
        per.setdefault(t["user"], {"income": 0, "expense": 0})
        per[t["user"]][t["kind"]] += t["amount"]

    bad = []
    for m in D["members"]:
        p = per.get(m["id"], {"income": 0, "expense": 0})
        if p["income"] != m["income"]:
            bad.append("%s 收入：彙總 %d ≠ 明細 %d" % (m["name"], m["income"], p["income"]))
        if p["expense"] != m["expense"]:
            bad.append("%s 支出：彙總 %d ≠ 明細 %d" % (m["name"], m["expense"], p["expense"]))
    assert not bad, "\n".join(bad)


def test_每個人的月數列最後一個月要等於本月彙總():
    """近 6 個月那張圖的最後一根，必須等於它上面的 KPI。

    以前 monthly 是一份固定的全家數列，個人總覽和家庭總覽拿到一樣的東西，
    最後一個月是 131,000／96,400，跟個人 KPI（68,000／41,230）直接矛盾。
    """
    D = _load_data()
    bad = []
    for m in D["members"]:
        series = m.get("monthly")
        assert series, "%s 沒有 monthly 數列" % m["name"]
        last = series[-1]
        if last["income"] != m["income"] or last["expense"] != m["expense"]:
            bad.append("%s 最後一個月 %d/%d ≠ 本月 %d/%d" % (
                m["name"], last["income"], last["expense"], m["income"], m["expense"]))
    assert not bad, "\n".join(bad)


def test_建議引用的數字要對得上明細():
    """建議是 LLM 寫的文字，但裡面的數字是後端算的——算錯就是說謊。"""
    D = _load_data()
    exp = [t for t in D["transactions"] if t["kind"] == "expense"]

    def cat_total(cat_id, user=None):
        return sum(t["amount"] for t in exp
                   if t["cat"] == cat_id and (user is None or t["user"] == user))

    assert cat_total("C03") == 18500, "居住應為 18,500（建議 A2 引用）"
    assert cat_total("C05") == 7480, "娛樂應為 7,480（建議 A1 引用）"
    assert cat_total("C05", "U3") == 6880, "宇涵的娛樂應為 6,880（建議 A1 引用）"
    assert cat_total("C01", "U4") == 2340, "宇軒的餐飲應為 2,340（建議 A3 引用）"

    total = sum(t["amount"] for t in exp)
    assert total == 96400, "全家支出應為 96,400（建議 A4 引用），實際 %d" % total


def test_統計不可以再讀成員的彙總欄位():
    """summary 的收支一律從明細算。

    回頭讀 members[].income/expense 就會讓 KPI 和圖表再次分家。
    """
    api = read("frontend/js/api.js")
    mo = re.search(r"summary: function \(f\) \{(.*?)\n    \},", api, re.S)
    assert mo, "api.js 裡找不到 summary"
    body = mo.group(1)

    assert "txSum(" in body, "summary 沒有用 txSum() 從明細算"
    for bad in ("m.income", "m.expense", "mm.income :", "? m.income"):
        assert bad not in body, "summary 又去讀彙總欄位了：" + bad


def test_選了單一帳本時不可以畫近六個月():
    """每個人的月數列沒有分帳本，硬畫出來就是一張假的圖。"""
    api = read("frontend/js/api.js")
    assert "var scoped = !(f.groupId && f.groupId !== 'all');" in api, \
        "summary 沒有判斷是否只看單一帳本"
    assert "}) : null;" in api, "選了單一帳本時 monthly 應該回 null"
