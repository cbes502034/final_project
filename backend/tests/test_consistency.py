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


def test_手冊上的路由總數也要對():
    """手冊開頭的標籤、API 目錄那段各寫了一次總數。

    ⚠️ 加了四支平台管理的路由之後，這兩處停在 59——分項的數字都對，只有總數沒人改。
    """
    from app.ownership import all_routes

    n = len(list(all_routes()))
    handbook = read("frontend/docs/index.html")
    found = re.findall(r"(\d+) 支路由", handbook)
    assert found, "手冊裡找不到「N 支路由」"
    stale = sorted({x for x in found if int(x) != n})
    assert not stale, "手冊寫的路由總數 %s，ownership.py 是 %d 支" % ("、".join(stale), n)

    # API 瀏覽頁的開場與頁尾也各寫了一次
    api = read("frontend/docs/api.html")
    m1 = re.search(r"我們寫的 <b>(\d+) 支</b>", api)
    m2 = re.search(r"(\d+) ROUTES · 4 MODULES", api)
    assert m1 and m2, "API 瀏覽頁找不到路由總數"
    assert int(m1.group(1)) == n and int(m2.group(1)) == n,         "API 瀏覽頁寫 %s／%s 支，ownership.py 是 %d 支" % (m1.group(1), m2.group(1), n)


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


def test_可見範圍只有三條路_角色只打開家長之間():
    """看得到誰的全部紀錄：自己、我監管的人、同家庭的其他家長。

    ⚠️ 2026-09-14 使用者決定「家長之間本身就看得到」。
    但角色**只能**打開「家長 ↔ 家長」這一條：
      · 家長看子女，一樣要有監管關係
      · 子女不會因為角色看到任何人
    寫成 `if (role === 'parent') return 全家` 就會連子女一起打開。
    """
    api = read("frontend/js/api.js")
    mo = re.search(r"function visibleUsers\(meId\) \{(.*?)\n  \}", api, re.S)
    assert mo, "api.js 裡找不到 visibleUsers"
    body = mo.group(1)
    assert "guardianships" in body, "visibleUsers 沒有看 guardianships"
    assert "coParents(" in body, "visibleUsers 沒有算同家庭的家長"
    assert "role" not in body, "角色判斷只能放在 coParents 裡：\n" + body

    mo2 = re.search(r"function coParents\(meId\) \{(.*?)\n  \}", api, re.S)
    assert mo2, "api.js 裡找不到 coParents"
    cp = mo2.group(1)
    assert "me.role !== 'parent'" in cp, "我不是家長時 coParents 必須是空的"
    assert "m.role === 'parent'" in cp, "coParents 只能回家長，不能連子女一起回"
    assert "familyId" in cp, "coParents 必須限同一個家庭"


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
    assert "{ action: '建立帳本', parent: 'Y', child: 'Y' }" in data, \
        "建立帳本應該兩種角色都可以——記帳的分類方式不該由家裡的階級決定"


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
    # ⚠️ 三個檔案都要檢查。原本只看 data.js，結果 api.js 的註冊流程
    # 還在發 role: 'member'——新註冊的人，角色標籤會顯示 undefined。
    # ⚠️ 這裡**不能**用 _blank()：它會把字串塗白，而我們要找的正是
    # role: 'member' 這個字串本身——塗白等於自己把證據擦掉，
    # 測試會永遠通過。（寫錯過一次，反向驗證才發現。）
    for path in ("frontend/js/data.js", "frontend/js/api.js", "frontend/js/app.js"):
        assert "role: 'member'" not in read(path), \
            "%s 還在用 member 這個角色，它已經改名為 child" % path


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
        # ⚠️ 平台管理員沒有財務資料，這正是那個角色的定義——
        # 他能停權，但讀不到也沒有任何一筆帳。所以他不該有月數列。
        if m.get("isPlatformAdmin"):
            assert not m.get("monthly"), \
                "%s 是平台管理員，不該有財務數列" % m["name"]
            continue
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


# ===========================================================================
# 顏色
# ===========================================================================

_PAPER = "#F4F1EA"      # 背景
_CARD = "#FFFFFF"       # 卡片


def _luminance(hex_color):
    h = hex_color.lstrip("#")
    parts = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    parts = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4
             for x in parts]
    return 0.2126 * parts[0] + 0.7152 * parts[1] + 0.0722 * parts[2]


def _contrast(a, b):
    la, lb = _luminance(a), _luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _palette(prefix):
    """從 tokens.css 撈出一組語意色。

    ⚠️ 顏色現在住在 tokens.css，不在 data.js——
    data.js 只說「這是餐飲」，主題才決定餐飲長什麼樣。
    """
    css = read("frontend/css/tokens.css")
    return dict(re.findall(r"--(%s-[a-z]+):\s*(#[0-9A-Fa-f]{6})" % prefix, css))


def test_帳本顏色在米白上看得見():
    """小圓點這類非文字元素，對比至少要 3:1。

    上一版的色盤是深色主題留下來的亮彩：薄荷綠 #6EE7B7 在米白上只有
    1.35——那顆標示目前帳本的小圓點等於不存在。而且它不會報錯，
    只會讓人覺得「怎麼看不出現在在哪一本」。
    """
    books = _palette("book")
    assert len(books) >= 4, "帳本色盤太少：%d" % len(books)

    bad = []
    for name, c in sorted(books.items()):
        for bg, label in ((_PAPER, "米白"), (_CARD, "白卡")):
            r = _contrast(c, bg)
            if r < 3.0:
                bad.append("%s %s 在%s上只有 %.2f:1" % (name, c, label, r))
    assert not bad, "這些顏色太淡，小圓點會看不見：\n" + "\n".join(bad)


def test_帳本色與分類色要分得開():
    """兩套顏色會同時出現在圖表上，撞色就分不清誰是誰。

    分類回答「錢花在什麼」，帳本回答「這筆算哪一本帳」。
    區別靠**明度**不靠色相——色相不夠用，分類已經佔掉赭藍紫綠紅琥珀。
    """
    books = _palette("book")
    cats = _palette("cat")
    assert books and cats

    brightest = max(_luminance(c) for c in books.values())
    darkest = min(_luminance(c) for c in cats.values())
    assert brightest < darkest, (
        "帳本色必須整組比分類色暗：帳本最亮 %.4f，分類最暗 %.4f" % (brightest, darkest))

    overlap = set(books.values()) & set(cats.values())
    assert not overlap, "帳本色跟分類色撞色了：" + "、".join(sorted(overlap))


def test_顏色不可以再寫死在資料裡():
    """data.js 只存語意代號，色碼一律住在 tokens.css。

    寫死在資料裡的顏色是**資料**不是主題——換一套外觀的時候，
    圓餅圖和帳本圓點還是原來的顏色，跟整頁格格不入。
    這是換膚做得起來的前提。
    """
    data = read("frontend/js/data.js")
    stray = re.findall(r"color: '(#[0-9A-Fa-f]{6})'", data)
    assert not stray, "data.js 又出現寫死的色碼：" + "、".join(stray)

    # 用到的代號，tokens.css 裡都要有
    css = read("frontend/css/tokens.css")
    used = set(re.findall(r"color: '((?:cat|book)-[a-z]+)'", data))
    assert used, "data.js 裡找不到任何語意代號"
    missing = [t for t in sorted(used) if ("--%s:" % t) not in css]
    assert not missing, "這些代號在 tokens.css 裡沒有定義：" + "、".join(missing)


def test_顏色進畫面之前一定要過_tint():
    """顏色字串會被塞進 style="background:…"，那是 CSS 的情境。

    ⚠️ esc() 擋不住這裡——它只處理 HTML。所以 tint() 兼任過濾器，
    只放行 [a-z0-9-]。繞過它就等於開了一個 CSS 注入的口。
    """
    app = read("frontend/js/app.js")
    mo = re.search(r"function tint\(token\) \{(.*?)\n  \}", app, re.S)
    assert mo, "app.js 裡找不到 tint()"
    assert "replace(" in mo.group(1), "tint() 沒有過濾字元"

    # 從**資料**來的顏色（x.color / t.catColor 這種）一定要過 tint()。
    # 程式裡自己寫死的 var(--accent) 常數陣列不算——那不是使用者給的。
    raw = re.findall(r"style=\"(?:background|color|stroke):' \+ (?!tint\()"
                     r"([A-Za-z_$][\w$]*\.[\w$]*[Cc]olor)", app)
    assert not raw, "這些資料來源的顏色沒過 tint()：" + "、".join(sorted(set(raw)))


def test_現有帳本都用色盤裡的代號():
    """色盤是單一來源。種子資料自己挑一個不在盤裡的代號，
    就等於「表單給一套、資料用另一套」——那正是上一版的毛病。
    """
    data = read("frontend/js/data.js")
    block = data[data.index("  groupColors: ["):data.index("]", data.index("  groupColors: ["))]
    palette = set(re.findall(r"id: '([a-z-]+)'", block))
    assert palette, "找不到帳本色盤"

    used = re.findall(r"name: '[^']+', color: '([a-z-]+)', owner:", data)
    assert used, "找不到帳本的顏色"
    bad = [c for c in used if c not in palette]
    assert not bad, "這些帳本用了色盤外的代號：" + "、".join(bad)


def test_開帳本的表單不可以自己寫死一套顏色():
    """寫死的那一版跟種子資料完全是兩套，新開的帳本因此格格不入。"""
    app = read("frontend/js/app.js")
    mo = re.search(r"<select id=\"gnColor\">(.{0,400})", app, re.S)
    assert mo, "找不到開帳本的顏色選單"
    assert "groupColors" in mo.group(1), "顏色選單沒有讀 DATA.groupColors"


def test_app_js_不可以用裸的_DATA():
    """app.js 裡沒有 var DATA，只有 global.DATA。

    寫成裸的 DATA 不會有任何靜態錯誤，載入也正常——
    要等使用者點到那一段才 ReferenceError。
    """
    app = _blank(read("frontend/js/app.js"))     # 註解和字串裡的不算
    # 前面有 `.` 的（global.DATA）本來就被 lookbehind 排除了
    bare = re.findall(r"(?<![.\w$])DATA\b(?!_)", app)
    assert not bare, (
        "app.js 出現了 %d 處裸的 DATA，請改成 global.DATA" % len(bare))


def test_帳本裡面沒有權限階級():
    """在一本帳裡的人，看得到的東西一樣，也都記得進去。

    要「只能看不能改」的關係，那叫監管（guardianships），
    不是靠帳本成員做半套的唯讀。

    原本 group_members 有一個 can_write 欄位，但沒有任何程式讀它——
    一個寫在文件上卻不存在的權限，比沒有更糟：讀文件的人會以為有。
    """
    data = _blank(read("frontend/js/data.js"))    # 註解裡提到它是可以的
    assert "can_write" not in data, \
        "can_write 又出現了。帳本內不分讀寫；要唯讀就用監管關係"

    for path in ("frontend/js/api.js", "frontend/js/app.js"):
        src = read(path)
        assert "canWrite" not in src and "can_write" not in src, \
            "%s 出現了帳本層級的寫入權限" % path


def test_監管的通知不受帳本限制():
    """父母收得到子女的消息，不管子女記在哪一本帳。

    這是監管存在的意義。做臨時帳本的時候最容易弄丟它——
    一旦通知改成只看「我也在那本帳裡」，被監管的人開一本新帳就消音了。
    """
    api = read("frontend/js/api.js")
    mo = re.search(r"type: 'ward_transaction'", api)
    assert mo, "找不到 ward_transaction"
    head = api[max(0, mo.start() - 1400):mo.start()]
    assert "wards.indexOf(t.user) >= 0" in head, "監管通知應該只看監管關係"
    assert "vgs.indexOf(t.group)" not in head, \
        "監管通知被加上帳本篩選了——被監管的人另開一本帳就收不到通知"


def test_總覽統計建議各自回答一個問題_不重複():
    """三頁照**問題**分工，每樣資料只出現在一個地方：

        總覽       這個月現在怎樣   疊卡（還可以花＋收入支出）、常用功能、預算、今天的紀錄（全家模式多每個人）
        統計       過去的趨勢       月／年對照、趨勢、分類圓餅
        財務建議   那該怎麼辦       建議清單

    家庭跟個人是同一套畫面，只差範圍。以前另外有一頁「家庭總覽」，
    跟總覽的內容幾乎一樣、又跟統計互相重複，已經併進總覽的「全家」模式。
    """
    app = read("frontend/js/app.js")
    assert "function vFamily(" not in app, "家庭總覽已經併進總覽的「全家」模式，不該再有獨立的一頁"
    assert "family:" not in re.search(r"var ROUTES = \{(.*?)\};", app, re.S).group(1)

    mo = re.search(r"function vHome\(\) \{(.*?)\n  \}", app, re.S)
    assert mo, "找不到 vHome"
    home = mo.group(1)
    for bad in ("donut(", "barChart(", "txTable(", "recentList("):
        assert bad not in home, "總覽不該放 %s——圖在統計、紀錄在收支明細" % bad
    assert "memberTable(" in home, "總覽的全家模式要有「每個人的這個月」"

    mo2 = re.search(r"function vStats\(\) \{(.*?)\n  \}\n", app, re.S)
    assert mo2, "找不到 vStats"
    stats = mo2.group(1)
    assert "donut(" in stats and "barChart(" in stats, "統計要有分類圓餅與趨勢"
    assert "memberBar(" not in stats and "memberTable(" not in stats, \
        "統計是按時間和分類看，不是按人"


def test_全家模式只整理資訊不能編輯():
    """家庭是整理資訊，沒有「記一筆」，也沒有任何輸入框。

    「記一筆」出現在三個地方：常用功能的第一顆、電腦版頂列、手機底部分頁中間那顆。
    全家模式三個都要收起來——記帳永遠是記自己的。
    """
    app = read("frontend/js/app.js")
    home = re.search(r"function vHome\(\) \{(.*?)\n  \}", app, re.S).group(1)
    assert "fam ? null : { quick: true" in home, "全家模式的儀表板不該有「記一筆」按鈕"
    assert "<input" not in home and "<select" not in home, "總覽出現了可以編輯的欄位"
    for fn in ("memberTable", "tile"):
        body = re.search(r"function %s\(.*?\) \{(.*?)\n  \}" % fn, app, re.S).group(1)
        assert "<input" not in body and "<select" not in body, "%s 裡出現了可以編輯的欄位" % fn

    head = re.search(r"function head\(t, sub, act\) \{(.*?)\n  \}", app, re.S).group(1)
    assert "classList.toggle('in-family'" in head, "切到全家時 body 要標記 in-family"
    css = read("frontend/css/app.css")
    assert "body.in-family .appbar__add" in css, "全家模式頂列的「記一筆」沒有收起來"
    assert "body.in-family .tabbar__add" in css, "全家模式手機底部分頁的「記一筆」沒有收起來"


def test_子女只有我的模式():
    """「我／全家」切換只給有監管對象的家長。"""
    app = read("frontend/js/app.js")
    body = re.search(r"function canFamily\(m\) \{(.*?)\n  \}", app, re.S).group(1)
    assert "'parent'" in body and "visible" in body


def test_結算不可以搬動任何一筆紀錄():
    """結算只是把帳本標記結束，不是把紀錄換一本帳。

    最早的設計是「結算＝把紀錄歸戶到個人時間軸」，那會改變 group_id，
    也就改變了誰看得到。後來可見範圍從交集改成聯集——監管者本來就看得到
    監管對象在任何帳本的紀錄——那個顧慮自己消失了，結算也就不必搬東西。

    搬動紀錄是不可逆的；標記結束是可逆的。能不搬就不要搬。
    """
    api = read("frontend/js/api.js")
    mo = re.search(r"settleGroup: function \(gid\) \{(.*?)\n    \},", api, re.S)
    assert mo, "api.js 裡找不到 settleGroup"
    body = mo.group(1)

    for bad in ("t.group =", ".group =", "transactions"):
        assert bad not in body, "結算動到紀錄了：" + bad
    assert "s.settled" in body, "結算應該只寫一筆結算標記"


def test_活動帳本一定要有結束日():
    """沒有結束日的活動帳本永遠不會到期，也就永遠不會被結算——
    那它跟常設帳本沒有差別，只是多一個標籤。
    """
    api = read("frontend/js/api.js")
    assert "if (kind === 'temp' && !p.endsOn) throw new Error('活動帳本要有結束日');" in api, \
        "建立活動帳本時沒有擋掉缺少結束日的情況"


def test_帳本沒有圖示方塊():
    """**所有**帳本都沒有圖示，不只活動帳本。

    名字已經說清楚是哪一本了，再擺一個寫著同一個字的方塊只是佔位。
    顏色靠切換器上的小圓點就夠。

    這裡連欄位一起擋掉：一個沒有任何地方顯示的欄位，
    下一個人會以為它有用而去填它——跟 can_write 同一種問題。
    """
    data = read("frontend/js/data.js")
    block = data[data.index("  groups: ["):data.index("],", data.index("  groups: ["))]
    assert "icon" not in block, "種子資料的帳本還帶著 icon"
    assert "['icon'" not in data[data.index("{ t: 'groups'"):
                                 data.index("{ t: 'group_members'")], \
        "groups 的資料表還留著 icon 欄位"

    api = read("frontend/js/api.js")
    mo = re.search(r"createGroup: function \(p\) \{(.*?)\n    \},", api, re.S)
    assert mo, "api.js 裡找不到 createGroup"
    assert "icon" not in mo.group(1), "建立帳本時還在產生 icon"

    app = read("frontend/js/app.js")
    for fn in ("ledgerRow", "ledgerBody"):
        mo2 = re.search(r"function %s\(g\) \{(.*?)\n  \}" % fn, app, re.S)
        assert mo2, "app.js 裡找不到 %s" % fn
        assert "g.icon" not in mo2.group(1), "帳本（%s）還在畫圖示方塊" % fn


def test_帳本通知預設是關的():
    """家用帳本本月 31 筆 × 3 個其他成員 = 93 則。預設開就是洗版。"""
    data = read("frontend/js/data.js")
    assert "notify: true" not in data, "種子資料裡有帳本預設開著通知"
    assert data.count("notify: false") >= 8, "帳本成員應該都明確標記 notify: false"


def test_主頁不可以變成繞過登入的破口():
    """主頁是**登入頁的第一個狀態**，不是一個新的公開路由。

    如果把它加進 OPEN，沒登入的人就多一個能停留的地方；
    而真正危險的是有人順手把別的頁也加進去。這裡把 OPEN 釘死。
    """
    app = read("frontend/js/app.js")
    mo = re.search(r"var OPEN = \[([^\]]*)\]", app)
    assert mo, "app.js 裡找不到 OPEN"
    opens = re.findall(r"'([^']+)'", mo.group(1))
    assert opens == ["login", "register"],         "沒登入能看的頁被改了：%s" % opens

    assert "landing:" not in app, "主頁不該是一個獨立路由"


def test_主頁到表單是原地渲染不是跳轉():
    """使用者要的是「不用跳轉」——按下去就換，不要白屏。

    所以按鈕不可以去改 location.hash，也不可以重新載入。
    """
    app = read("frontend/js/app.js")
    mo = re.search(r"if \(t\.closest\('#lpGo'\)\) \{(.*?)\n      return;", app, re.S)
    assert mo, "找不到「開始使用」的處理"
    body = mo.group(1)
    for bad in ("location.hash", "location.href", "location.replace", "reload"):
        assert bad not in body, "「開始使用」去動網址了：" + bad
    assert "vLogin()" in body, "應該直接重畫成登入表單"


def test_主頁的插圖不外連圖檔():
    """插圖用 SVG 畫在頁面裡：要跟著米白主題走、放大不能糊，
    而且外連圖檔會多一個載入失敗的可能。
    """
    app = read("frontend/js/app.js")
    mo = re.search(r"function ledgerArt\(\) \{(.*?)\n  \}", app, re.S)
    assert mo, "找不到 ledgerArt"
    body = mo.group(1)
    assert "<svg" in body, "插圖不是 SVG"
    for bad in ("<img", "url(", "http://", "https://", ".png", ".jpg", ".svg\""):
        assert bad not in body, "插圖外連了資源：" + bad


def test_每一個用到_monthly_的地方都要防著它是_null():
    """summary 在選了單一帳本時回 monthly: null（不畫假圖）。

    ⚠️ 這個防護漏掉過：家庭總覽加了 if (d.monthly)，統計頁沒加，
    於是「選一本帳 → 打開統計」整頁變成「讀取失敗」，
    而且本機剛好停在「全部帳本」所以測不出來——線上才爆。

    所以規則改成：**呼叫端不用記得防**，barChart 自己接得住 null，
    而任何 .monthly.map( 這種直接串下去的寫法都不允許。
    """
    app = read("frontend/js/app.js")

    unguarded = re.findall(r"\.monthly\.map\(", app)
    assert not unguarded, "有人直接對 monthly 串 .map()，它可能是 null"

    mo = re.search(r"function barChart\(rows\) \{(.*?)\n    var max", app, re.S)
    assert mo, "app.js 裡找不到 barChart"
    assert "!rows" in mo.group(1), "barChart 沒有防住 null／空陣列"


# ===========================================================================
# 停權與稽核：用 node 把 mock 真的跑一次
# ===========================================================================
#
# 前面的測試大多是讀原始碼找字串。停權這件事不能只這樣驗——
# 「停權了但重新整理就失效」「停權了但他還登得進來」都是**字串完全正確、
# 行為完全錯誤**的情況。所以這裡真的登入、真的停權、真的重新載入一次。

_ADMIN_DRIVER = r"""
const [dataJs, apiJs] = process.argv.slice(2);

// 瀏覽器環境的最小替身
const store = new Map();
global.localStorage = {
  getItem: k => store.has(k) ? store.get(k) : null,
  setItem: (k, v) => store.set(k, String(v)),
  removeItem: k => store.delete(k)
};
global.document = { querySelector: () => null };      // 沒有 api-base → mock
global.setTimeout = fn => setImmediate(fn);           // 不要真的等延遲

function boot() {
  // 重新 require 等於重新整理頁面：closure 裡的 state 會歸零，只剩 localStorage
  delete require.cache[require.resolve(dataJs)];
  delete require.cache[require.resolve(apiJs)];
  global.window = {};
  require(dataJs);
  require(apiJs);
  return window.API;
}

async function fails(p) {
  try { await p; return null; } catch (e) { return { msg: e.message, status: e.status || null }; }
}

(async () => {
  const out = {};
  const PW = 'password123';
  let API = boot();

  await API.login({ email: 'admin@fambudget.tw', password: PW });
  out.me = (await API.me()).user;
  out.users = (await API.adminUsers()).users;

  out.noReason     = await fails(API.suspendUser('U4', ''));
  out.spaceReason  = await fails(API.suspendUser('U4', 'a          b'));
  out.suspendAdmin = await fails(API.suspendUser('U0', '測試停權管理員'));
  await API.suspendUser('U4', '  重複   張貼廣告  ');
  out.auditAfterSuspend = (await API.audit()).logs;

  await API.logout();
  out.loginWhileSuspended = await fails(API.login({ email: 'yuxuan@lin.tw', password: PW }));
  out.wrongPwLeaks = await fails(API.login({ email: 'yuxuan@lin.tw', password: 'x' }));

  API = boot();                                        // 重新整理
  out.loginAfterReload = await fails(API.login({ email: 'yuxuan@lin.tw', password: PW }));

  await API.login({ email: 'jianguo@lin.tw', password: PW });
  out.parentAdminUsers = await fails(API.adminUsers());
  out.parentAudit      = await fails(API.audit());
  out.parentSuspend    = await fails(API.suspendUser('U3', '家長想停小孩'));

  await API.login({ email: 'admin@fambudget.tw', password: PW });
  // 用 fails() 包起來：停權如果在重新整理時消失了，這一步會丟錯，
  // 要讓底下那條「重新整理之後停權就失效了」講出真正的原因，而不是整支當掉
  out.unsuspend = await fails(API.unsuspendUser('U4'));
  out.auditAfterUnsuspend = (await API.audit()).logs;
  out.loginAfterUnsuspend = await fails(API.login({ email: 'yuxuan@lin.tw', password: PW }));

  // 已經登入的人被停權：下一次請求就要被踢出去，不是等他下次登入
  await API.login({ email: 'admin@fambudget.tw', password: PW });
  await API.suspendUser('U4', '已登入中被停權');
  const raw = JSON.parse(localStorage.getItem('fambudget.state.v1'));
  raw.me = 'U4'; raw.auth = { loggedIn: true };
  localStorage.setItem('fambudget.state.v1', JSON.stringify(raw));
  API = boot();
  out.authStateOfSuspended = await API.authState();

  process.stdout.write(JSON.stringify(out));
})().catch(e => { console.error(e); process.exit(1); });
"""


_ADMIN_RUN = {}


def _run_admin_flow():
    """整個流程只跑一次，底下幾支測試共用結果。"""
    import json
    import shutil
    import subprocess
    import tempfile

    if "out" in _ADMIN_RUN:
        return _ADMIN_RUN["out"]
    if not shutil.which("node"):
        import pytest
        pytest.skip("這台機器沒有 node")

    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                     encoding="utf-8") as fh:
        fh.write(_ADMIN_DRIVER)
        tmp = fh.name
    res = subprocess.run(
        ["node", tmp,
         os.path.join(REPO, "frontend", "js", "data.js"),
         os.path.join(REPO, "frontend", "js", "api.js")],
        capture_output=True)
    assert res.returncode == 0, res.stderr.decode("utf-8", "replace")
    _ADMIN_RUN["out"] = json.loads(res.stdout.decode("utf-8"))
    return _ADMIN_RUN["out"]


def test_平台管理員拿到的帳號清單裡沒有任何金額():
    """停權是關門，不是配鑰匙。後端不回，前端就畫不出來——不是藏起來。"""
    out = _run_admin_flow()
    assert out["me"]["isPlatformAdmin"] is True

    money = {"income", "expense", "budget", "savingsGoal", "monthly",
             "balance", "amount", "transactions", "allowance"}
    for u in out["users"]:
        leaked = money & set(u)
        assert not leaked, "%s 的資料裡帶著金額欄位：%s" % (u["name"], leaked)
    assert all(u["id"] != "U0" for u in out["users"]), "清單裡不該有平台管理員自己"


def test_停權沒有理由就不能執行():
    out = _run_admin_flow()
    assert out["noReason"], "沒寫理由也停權成功了"
    assert out["spaceReason"], "用空白湊字數也停權成功了"
    assert out["suspendAdmin"], "平台管理員被停權了——那就沒有人能解除了"


def test_停權與解除都會寫進稽核():
    out = _run_admin_flow()
    top = out["auditAfterSuspend"][0]
    assert top["action"] == "suspend_user" and top["target"] == "U4"
    assert top["note"] == "重複 張貼廣告", "稽核裡的理由沒有經過整理：%r" % top["note"]
    assert top["actorName"] == "系統管理員"

    top2 = out["auditAfterUnsuspend"][0]
    assert top2["action"] == "unsuspend_user" and top2["target"] == "U4", \
        "解除停權沒有留下紀錄——「誰放他回來的」跟「誰停的他」一樣重要"


def test_停權真的擋得住登入_而且重新整理之後還在():
    """⚠️ 這條抓到過：save()/load() 沒有存 suspended，
    停權在同一頁看起來有效，重新整理之後被停的人就登得進來了。"""
    out = _run_admin_flow()
    assert out["loginWhileSuspended"] and "停權" in out["loginWhileSuspended"]["msg"]
    assert out["loginAfterReload"] and "停權" in out["loginAfterReload"]["msg"], \
        "重新整理之後停權就失效了"
    assert out["loginAfterUnsuspend"] is None, "解除停權之後還是登不進去"


def test_密碼錯的時候不可以透露帳號被停權():
    """停權檢查要在密碼驗證之後。反過來就能拿 email 試出誰被停權了。"""
    out = _run_admin_flow()
    assert out["wrongPwLeaks"], "密碼錯還登入成功？"
    assert "停權" not in out["wrongPwLeaks"]["msg"], \
        "密碼錯的時候就回了「已被停權」，等於送出一支停權帳號查詢器"


def test_已經登入的人被停權_下一次請求就會被踢出去():
    out = _run_admin_flow()
    assert out["authStateOfSuspended"]["loggedIn"] is False, \
        "被停權的人還維持著登入狀態——停權變成「下次登入才生效」"


def test_稽核時間是當地時間不是_UTC():
    """toISOString() 是 UTC：下午三點停的權，在台灣會記成早上七點。

    ⚠️ 瀏覽器實測時抓到的。稽核紀錄就是拿來對時間的，差 8 小時等於紀錄是錯的。
    這裡用 TZ=Asia/Taipei 跑一次，確認寫進去的時間跟當地時鐘一樣。
    """
    import json
    import shutil
    import subprocess
    import tempfile

    if not shutil.which("node"):
        import pytest
        pytest.skip("這台機器沒有 node")

    driver = _ADMIN_DRIVER.split("(async () => {")[0] + r"""
(async () => {
  const API = boot();
  await API.login({ email: 'admin@fambudget.tw', password: 'password123' });
  const before = new Date();
  await API.suspendUser('U3', '測試稽核時間');
  const top = (await API.audit()).logs[0];
  const p = n => String(n).padStart(2, '0');
  const local = before.getFullYear() + '-' + p(before.getMonth() + 1) + '-' + p(before.getDate()) +
                ' ' + p(before.getHours()) + ':';
  process.stdout.write(JSON.stringify({ at: top.at, localPrefix: local }));
})().catch(e => { console.error(e); process.exit(1); });
"""
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                     encoding="utf-8") as fh:
        fh.write(driver)
        tmp = fh.name
    res = subprocess.run(
        ["node", tmp,
         os.path.join(REPO, "frontend", "js", "data.js"),
         os.path.join(REPO, "frontend", "js", "api.js")],
        capture_output=True, env=dict(os.environ, TZ="Asia/Taipei"))
    assert res.returncode == 0, res.stderr.decode("utf-8", "replace")
    out = json.loads(res.stdout.decode("utf-8"))
    assert out["at"].startswith(out["localPrefix"]), \
        "稽核時間 %s 跟當地時間 %s 對不上——大概又用了 toISOString()" % (
            out["at"], out["localPrefix"])


def test_家長不能用平台管理的任何一支():
    """家長是家庭治理權限，跟平台管理員完全分開。"""
    out = _run_admin_flow()
    for k in ("parentAdminUsers", "parentAudit", "parentSuspend"):
        assert out[k], "家長呼叫 %s 成功了" % k
        assert out[k]["status"] == 403, "%s 應該回 403" % k


def test_mock_存檔與讀檔的欄位要成對():
    """load() 讀回哪些欄位，save() 就要寫出哪些欄位。

    這一類錯誤不會報錯：少存一個欄位，功能在同一頁完全正常，
    **重新整理才消失**。suspended／audit 就是這樣漏掉的。
    """
    api = read("frontend/js/api.js")
    mo = re.search(r"\[('newGroups'.*?)\]\.forEach", api, re.S)
    assert mo, "api.js 的 load() 裡找不到要讀回的欄位清單"
    restored = re.findall(r"'(\w+)'", mo.group(1))

    mo2 = re.search(r"function save\(\) \{(.*?)\n  \}", api, re.S)
    assert mo2, "api.js 裡找不到 save()"
    missing = [k for k in restored if not re.search(r"\b%s:" % k, mo2.group(1))]
    assert not missing, "load() 會讀回、但 save() 沒有寫出：" + "、".join(missing)


def test_規格文件的路由清單由_ownership_產生():
    """docs/01 的 6-2 總表與 6-3 各領域清單，一律由 tools/sync_spec.py 產生。

    這兩段手動維護過，結果 ownership.py 已經 17/18/13/15，
    文件還停在 8/8/10/9——差了一倍，而且沒有任何測試抓到。
    """
    import subprocess
    import sys

    res = subprocess.run(
        [sys.executable, os.path.join(REPO, "backend", "tools", "sync_spec.py"), "--check"],
        capture_output=True, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    assert res.returncode == 0, res.stdout.decode("utf-8", "replace")


def test_輸入框不可以留著星空主題的深色底():
    """換成米白主題時，有三個輸入框的底色沒換到：rgba(5,6,10,.5)。

    深底配深字，在米白上變成一塊灰色方塊，數字幾乎讀不到——
    帳本頁每一本帳的「月目標」就是這樣。沒有報錯，只是看起來髒。
    輸入框的底色一律用 --sunk。
    """
    css = read("frontend/css/app.css")
    leftovers = re.findall(r"[^\n]*background:\s*rgba\(\s*5\s*,\s*6\s*,\s*10[^\n]*", css)
    assert not leftovers, "還有星空主題留下來的深色底：\n" + "\n".join(leftovers)


def test_沒有側欄_原本的每個功能都嵌在儀表板上():
    """像銀行 App：沒有側欄，總覽就是儀表板。

    以前側欄（電腦）＋底部分頁與「更多」面板（手機）兩套導覽並存；
    現在只有一套——總覽上的功能按鈕，加上右上角的帳號選單。
    這個測試確保拆掉側欄的時候，沒有哪一頁因此變得「進不去」。
    """
    html = read("frontend/index.html")
    for gone in ('class="rail"', 'class="tabs"', 'id="sheet"', 'id="moreBtn"', 'id="logout2"'):
        assert gone not in html, "側欄／手機底部分頁還留著：" + gone
    assert 'class="appbar"' in html and 'id="acctPanel"' in html

    app = read("frontend/js/app.js")
    assert "sheetOpen" not in app and "fambudget.rail" not in app, "側欄與「更多」面板的程式沒拆乾淨"
    home = re.search(r"function vHome\(\) \{(.*?)\n  \}", app, re.S).group(1)
    tiles = set(re.findall(r"nav: '(\w+)'", home))

    menu = re.search(r'<div class="acctm__p" id="acctPanel" hidden>(.*?)\n        </div>', html, re.S).group(1)
    in_menu = set(re.findall(r'data-nav="(\w+)"', menu))

    routes = re.search(r"var ROUTES = \{(.*?)\};", app, re.S).group(1)
    pages = set(re.findall(r"(\w+): v\w+", routes))
    # 登入／註冊沒登入才看得到；member 是從家庭成員點進去的；admin 只有平台管理員（登入就直接導過去）
    need = pages - {"login", "register", "member", "admin"}
    missing = need - tiles - in_menu
    assert not missing, "這些頁面拆掉側欄之後進不去了：%s" % sorted(missing)
    assert "quick: true" in home, "儀表板上要有「記一筆」"
    assert "docs/guide.html" in home and 'href="docs/guide.html"' in menu
    assert 'href="docs/index.html"' in menu and 'id="logout"' in menu

    # 其他頁面要能回到總覽；總覽本身不需要那顆鈕
    assert 'id="homeBtn"' in html
    route = re.search(r"function render\(\) \{(.*?)\n      \}", app, re.S).group(1)
    assert "hb.hidden = page === ''" in route

    # 平台管理員沒有財務頁：帳號選單裡的「個人資料／家庭成員」和記一筆都不給
    css = read("frontend/css/app.css")
    assert "body.is-admin .acctm__habit" in css and "body.is-admin .acctm__fam" in css
    assert "body.is-admin .appbar__add" in css


def test_平台管理員與一般使用者的頁面互不相通():
    """管理員登入後落在「我的總覽」會是一頁全部是 0 的空殼；
    一般使用者打 #/admin 會拿到 403。兩邊都要在路由閘擋掉。

    ME 在登出與登入時都要清掉，否則路由閘會拿上一個人的身分判斷——
    管理員登出、家長登入的那一瞬間，家長會被送去 #/admin。
    """
    app = read("frontend/js/app.js")
    mo = re.search(r"function paint\(\) \{(.*?)\n  \}\n", app, re.S)
    assert mo, "app.js 裡找不到 paint()"
    body = mo.group(1)
    assert "admin && page !== 'admin'" in body, "路由閘沒有把管理員送去平台管理"
    assert "!admin && page === 'admin'" in body, "路由閘沒有擋一般使用者進平台管理"

    mo2 = re.search(r"function afterLogin\(d\) \{(.*?)\n  \}", app, re.S)
    assert mo2 and "ME = null" in mo2.group(1), "登入之後沒有清掉上一個人的身分"
    mo3 = re.search(r"API\.logout\(\)\.then\(function \(\) \{(.*?)\n      \}\);", app, re.S)
    assert mo3 and "ME = null" in mo3.group(1), "登出之後沒有清掉身分"

    mo4 = re.search(r"function tourAsk\(\) \{(.*?)\n  \}", app, re.S)
    assert mo4 and "isPlatformAdmin" in mo4.group(1), \
        "導覽會對管理員出現——它的每一步都指向他看不到的財務功能"


def test_帳本頁進來只看得到帳本():
    """一本帳平常只佔一行，點開才有成員、月目標、通知、結算。

    成員管理也在展開後的內容裡——以前另外有一個「誰在哪一本帳裡」區塊，
    同一本帳的資訊被拆成上下兩處。
    """
    app = read("frontend/js/app.js")
    mo = re.search(r"function vGroups\(\) \{(.*?)\n  \}\n", app, re.S)
    assert mo, "app.js 裡找不到 vGroups"
    body = mo.group(1)

    assert "foldBlock('gnew', '常設帳本'" in body, "「開一本」應該掛在常設帳本的標題上"
    assert "ledgerList(" in body, "帳本清單應該是收合列"
    assert "'誰在哪一本帳裡'" not in app, "「誰在哪一本帳裡」已經併進每一本帳的展開內容"
    assert "<table" not in body, "帳本不用表格"
    assert "foldRestore()" in body, "重畫之後沒有 foldRestore()"

    lb = re.search(r"function ledgerBody\(g\) \{(.*?)\n  \}", app, re.S).group(1)
    assert "data-gdel" in lb and "data-gaddsel" in lb, "成員的加減應該在帳本展開的內容裡"

    plain = re.findall(r'<h2 class="sec__t">([^<\']+)', body)
    assert set(plain) <= {"活動帳本"}, "帳本頁多了攤開的區塊：%s" % plain


def test_不再出現監視感的提示語():
    """這是一個家庭，不是監獄。

    「林建國 可以看到你的完整收支明細」這種句子本意是透明，
    讀起來卻是被盯著。關係本身在「成員與權限」都查得到，不需要在每一頁提醒。
    """
    app = read("frontend/js/app.js")
    for bad in ("可以看到你的完整收支明細", "誰看得到你的紀錄</div>", "不是每個人都達標",
                "存不到自己的目標", "目標由你代設", "系統不提供隱藏監管", "不會偷偷發生"):
        assert bad not in app, "還留著：" + bad


def test_標題三層要真的拉得開():
    """之前頁面 17px、區塊 15.5px、卡片 15px，三層只差一兩個像素，分不出來。"""
    css = read("frontend/css/tokens.css")
    size = dict((k, float(v)) for k, v in re.findall(r"--(h[123]):\s*([\d.]+)px", css))
    assert size["h1"] / size["h2"] >= 1.4, size
    assert size["h2"] / size["h3"] >= 1.25, size


def test_預算的已花一律從明細算():
    """林建國的交通曾經寫死 3,250，明細加起來是 15,150。"""
    data = read("frontend/js/data.js")
    block = data[data.index("  budgets: ["):data.index("],", data.index("  budgets: ["))]
    assert "used:" not in block, "data.js 的預算又存了已花多少"

    D = _load_data()
    spent = {}
    for tx in D["transactions"]:
        if tx["kind"] == "expense" and tx["date"].startswith(D["meta"]["period"]):
            key = (tx["user"], tx["cat"])
            spent[key] = spent.get(key, 0) + tx["amount"]
    api = read("frontend/js/api.js")
    body = re.search(r"    budgets: function \(f\) \{(.*?)\n    \},", api, re.S).group(1)
    assert "s.transactions" in body and "used:" in body, "API 的預算沒有從明細算"
    # 建議引用的預算數字要跟明細一致
    assert spent[("U1", "C02")] == 15150
    assert spent[("U3", "C05")] == 6880


def test_個人建議只給本人_全家建議只給家長():
    """子女不會看到寫給家長的全家建議——那幾則會點名。"""
    api = read("frontend/js/api.js")
    body = re.search(r"    advices: function \(f\) \{(.*?)\n    \},", api, re.S).group(1)
    assert "if (a.scope === 'family') return fam;" in body
    assert "if (a.user === s.me) return !fam;" in body

    D = _load_data()
    # 還沒加入家庭、也還沒有任何紀錄的人（示範用的林玉珍）沒有東西可以建議
    people = {m["id"] for m in D["members"] if not m.get("isPlatformAdmin") and m.get("familyId")}
    has = {a.get("user") for a in D["advices"] if a["scope"] == "user"}
    assert people <= has, "每個人都該有至少一則自己的建議，缺：%s" % (people - has)


def test_每一步導覽都找得到看得見的目標():
    """選單換了位置之後，導覽不可以指到不存在的元素。"""
    app = read("frontend/js/app.js")
    html = read("frontend/index.html")
    tour = re.search(r"var TOUR = \[(.*?)\];", app, re.S).group(1)
    for sel in re.findall(r"sel: '([^']+)'", tour):
        alts = [x.strip() for x in sel.split(",")]
        found = False
        for a in alts:
            m = re.match(r"^[.#]([\w-]+)", a)
            token = m.group(1) if m else a
            if ('id="%s"' % token in html) or (token in html) or (token in app):
                found = True
        assert found, "導覽步驟找不到目標：" + sel


def test_下拉面板浮在按鈕下面_不搬進版面():
    """帳本清單與通知面板曾經被搬進頂列和內容之間，佔真實空間把內容往下推。
    頁首改版後它們插在標題底下，一點開整頁就往下跳。"""
    app = read("frontend/js/app.js")
    assert "function placePanel(" not in app, "又把下拉面板搬進版面了"
    assert "classList.add('inflow')" not in app

    html = read("frontend/index.html")
    assert '<header class="top">' not in html, "頁首上方又多了一條獨立的頂列"
    tools = html[html.index('class="phead__tools"'):html.index('<div id="view">')]
    for part in ('id="gsw"', 'id="searchDrawer"'):
        assert part in tools, "帳本與搜尋要跟標題在同一行：少了 " + part
    # 通知每一頁都用得到，跟帳號選單一起放在頂列
    bar = html[html.index('<header class="appbar">'):html.index('</header>')]
    for part in ('id="bell"', 'id="bellPanel"', 'id="acctPanel"'):
        assert part in bar, "頂列少了 " + part

    css = read("frontend/css/app.css")
    for sel in (r"\.phead__tools \.gsw__p,\s*\.phead__tools \.bell__panel", r"\.appbar \.bell__panel"):
        rule = re.search(sel + r" \{([^}]*)\}", css)
        assert rule, "找不到 " + sel
        assert "position: absolute" in rule.group(1), "下拉面板應該用定位浮起來，不佔版面：" + sel
        assert "overflow-y: auto" in rule.group(1), "項目多的時候面板要自己捲，不能把頁面撐長：" + sel
    assert re.search(r"\.acctm__p \{[^}]*position: absolute", css), "帳號選單也要浮起來"


def test_電腦版的搜尋框不會被點掉():
    """點外面收起搜尋框只能在手機上。電腦版曾經點一下任何地方搜尋框就消失，旁邊的按鈕跟著位移。"""
    app = read("frontend/js/app.js")
    assert "if (narrowBar.matches && !t.closest('#searchDrawer') && !t.closest('#searchBtn'))" in app


# ===========================================================================
# 家庭綁定：用 node 把 mock 真的跑一次
# ===========================================================================

_FAMILY_DRIVER = _ADMIN_DRIVER.split("(async () => {")[0] + r"""
(async () => {
  const out = {}, PW = 'password123';
  let API = boot();
  await API.login({ email: 'jianguo@lin.tw', password: PW });
  out.u1Visible = (await API.me()).visible;
  out.lookGrandma = await API.lookupUser('yuzhen@mail.tw');
  out.lookSpouse = (await API.lookupUser('shufen@lin.tw')).status;
  out.lookAdmin = (await API.lookupUser('admin@fambudget.tw')).status;
  out.lookPartial = await fails(API.lookupUser('yuzhen'));
  out.send = await API.sendInvite({ userId: 'U5', role: 'child' });
  out.sendDup = await fails(API.sendInvite({ userId: 'U5', role: 'child' }));

  await API.login({ email: 'yuhan@lin.tw', password: PW });
  out.u3Visible = (await API.me()).visible;
  out.childLookup = await fails(API.lookupUser('yuzhen@mail.tw'));
  out.childCode = await fails(API.createInviteCode({ role: 'parent' }));
  await API.login({ email: 'shufen@lin.tw', password: PW });
  out.u2Visible = (await API.me()).visible;

  API = boot();
  await API.login({ email: 'yuzhen@mail.tw', password: PW });
  const inv = await API.invites();
  out.received = inv.received;
  out.beforeMembers = (await API.members());
  out.accept = await API.acceptInvite(inv.received[0].id);
  out.after = (await API.me()).user;
  out.afterVisible = (await API.me()).visible;

  await API.login({ email: 'jianguo@lin.tw', password: PW });
  out.u1SeesU5 = (await API.me()).visible.includes('U5');
  const code = await API.createInviteCode({ role: 'parent' });
  out.code = code;
  await API.register({ name: '林小姑', email: 'aunt@mail.tw', password: PW });
  out.newUser = (await API.me()).user;
  out.join = await API.joinFamily({ code: code.code.toLowerCase().replace('-', ' ') });
  out.newParentVisible = (await API.me()).visible;
  await API.register({ name: '陌生人', email: 'x@mail.tw', password: PW });
  out.reuse = await fails(API.joinFamily({ code: code.code }));
  out.strangerMembers = (await API.members()).members.map(m => m.id);
  const stranger = (await API.me()).user.id;
  await API.login({ email: 'jianguo@lin.tw', password: PW });
  out.addStranger = await fails(API.addGroupMember('G1', stranger));
  process.stdout.write(JSON.stringify(out));
})().catch(e => { console.error(e); process.exit(1); });
"""

_FAMILY_RUN = {}


def _run_family_flow():
    import json
    import shutil
    import subprocess
    import tempfile

    if "out" in _FAMILY_RUN:
        return _FAMILY_RUN["out"]
    if not shutil.which("node"):
        import pytest
        pytest.skip("這台機器沒有 node")
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
        fh.write(_FAMILY_DRIVER)
        tmp = fh.name
    res = subprocess.run(
        ["node", tmp, os.path.join(REPO, "frontend", "js", "data.js"),
         os.path.join(REPO, "frontend", "js", "api.js")], capture_output=True)
    assert res.returncode == 0, res.stderr.decode("utf-8", "replace")
    _FAMILY_RUN["out"] = json.loads(res.stdout.decode("utf-8"))
    return _FAMILY_RUN["out"]


def test_同家庭的家長互相看得到_子女不會因為角色看到人():
    out = _run_family_flow()
    assert "U2" in out["u1Visible"] and "U1" in out["u2Visible"], "家長之間應該互相看得到"
    assert out["u3Visible"] == ["U3"], "子女不會因為角色看到任何人：%s" % out["u3Visible"]
    assert not out["u1SeesU5"], "新加入的子女沒有監管關係，家長不該看得到全部"
    assert out["afterVisible"] == ["U5"], "新加入的子女只看得到自己"
    assert set(out["newParentVisible"]) == {out["newUser"]["id"], "U1", "U2"}, \
        "拿家長邀請碼加入的人，看得到的應該是自己和兩位家長（看不到孩子）"


def test_用帳號找人只接受完整email_也不回財務資料():
    out = _run_family_flow()
    assert out["lookPartial"], "只打一半的 email 也查得到——那就變成帳號名單了"
    assert set(out["lookGrandma"]["user"]) <= {"id", "name", "avatar", "avatarUrl"}, \
        "找人的回應帶了多餘的欄位：%s" % sorted(out["lookGrandma"]["user"])
    assert out["lookGrandma"]["status"] == "available"
    assert out["lookSpouse"] == "member"
    assert out["lookAdmin"] == "unavailable", "平台管理員不能被邀請，也不該說原因"


def test_只有家長能邀請_而且不能重複邀請():
    out = _run_family_flow()
    assert out["childLookup"] and out["childLookup"]["status"] == 403
    assert out["childCode"] and out["childCode"]["status"] == 403
    assert out["sendDup"] and out["sendDup"]["status"] == 409


def test_接受邀請之後加入家庭_身分由家長決定():
    out = _run_family_flow()
    assert out["beforeMembers"]["family"] is None, "還沒接受邀請前不該有家庭"
    assert [m["id"] for m in out["beforeMembers"]["members"]] == ["U5"], "沒有家庭時只列自己"
    assert out["received"][0]["familyName"] == "林家" and out["received"][0]["role"] == "child"
    assert out["after"]["familyId"] == "F1" and out["after"]["role"] == "child"


def test_邀請碼只能用一次_而且大小寫空白都吃得下():
    out = _run_family_flow()
    assert out["newUser"]["role"] is None and out["newUser"]["familyId"] is None, \
        "新註冊的人不該自動屬於任何家庭"
    assert out["join"]["role"] == "parent", "邀請碼要帶著家長決定的身分"
    assert out["reuse"], "同一組邀請碼被用了第二次"
    assert out["strangerMembers"] == [m for m in out["strangerMembers"] if m.startswith("U")] \
        and len(out["strangerMembers"]) == 1, "沒有家庭的人不該看到別人家的成員"
    assert out["addStranger"], "別人家的人被加進了自己家的帳本"


# ===========================================================================
# 移出家庭、退出家庭
# ===========================================================================
_LEAVE_DRIVER = _ADMIN_DRIVER.split("(async () => {")[0] + r"""
(async () => {
  const out = {}, PW = 'password123';
  let API = boot();
  await API.login({ email: 'jianguo@lin.tw', password: PW });
  out.removeSpouse = await fails(API.removeMember('U2'));
  out.remove = await API.removeMember('U3');
  out.u1Visible = (await API.me()).visible;
  out.u1Members = (await API.members()).members.map(m => m.id);
  out.u1Allowances = (await API.allowances()).allowances.map(a => a.wardId);
  out.u1Ledgers = (await API.groups({})).groups.map(g => [g.id, g.members]);
  await API.login({ email: 'yuhan@lin.tw', password: PW });
  out.u3Family = (await API.members()).family;
  out.u3Ledgers = (await API.groups({})).groups.map(g => [g.id, g.members]);
  out.u3Tx = (await API.transactions({ userId: 'U3' })).total;
  out.childRemove = await fails(API.removeMember('U4'));
  API = boot();
  await API.login({ email: 'jianguo@lin.tw', password: PW });
  out.reloadMembers = (await API.members()).members.map(m => m.id);
  await API.login({ email: 'yuxuan@lin.tw', password: PW });
  out.childLeave = await API.leaveFamily();
  await API.login({ email: 'shufen@lin.tw', password: PW });
  out.parentLeave = await API.leaveFamily();
  await API.login({ email: 'jianguo@lin.tw', password: PW });
  await API.sendInvite({ userId: 'U5', role: 'child' });
  await API.login({ email: 'yuzhen@mail.tw', password: PW });
  await API.acceptInvite((await API.invites()).received[0].id);
  await API.login({ email: 'jianguo@lin.tw', password: PW });
  out.lastParent = await fails(API.leaveFamily());
  process.stdout.write(JSON.stringify(out));
})().catch(e => { console.error(e); process.exit(1); });
"""


def _run_leave_flow():
    import json
    import shutil
    import subprocess
    import tempfile

    if not shutil.which("node"):
        import pytest
        pytest.skip("這台機器沒有 node")
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
        fh.write(_LEAVE_DRIVER)
        tmp = fh.name
    res = subprocess.run(
        ["node", tmp, os.path.join(REPO, "frontend", "js", "data.js"),
         os.path.join(REPO, "frontend", "js", "api.js")], capture_output=True)
    assert res.returncode == 0, res.stderr.decode("utf-8", "replace")
    return json.loads(res.stdout.decode("utf-8"))


def test_家長只能移出子女_不能移除另一位家長():
    out = _run_leave_flow()
    assert out["removeSpouse"] and out["removeSpouse"]["status"] == 403
    assert out["childRemove"] and out["childRemove"]["status"] == 403


def test_移出之後彼此看不到_但紀錄都還在():
    """人離開了，家人還看得到他後來記的每一筆——這就是不收掉監管與共用帳本的後果。"""
    out = _run_leave_flow()
    assert "U3" not in out["u1Visible"] and "U3" not in out["u1Members"]
    assert "U3" not in out["u1Allowances"], "監管關係結束了，零用金還在"
    for gid, members in out["u1Ledgers"]:
        assert "U3" not in members, "林宇涵還在家人的帳本 %s 裡" % gid
    for gid, members in out["u3Ledgers"]:
        assert members == ["U3"], "林宇涵自己開的帳本 %s 裡還有家人：%s" % (gid, members)
    assert out["u3Family"] is None
    assert out["u3Tx"] == 9, "移出家庭不可以刪紀錄"
    assert out["reloadMembers"] == ["U1", "U2", "U4"], "重新整理之後移出的狀態不見了"


def test_任何人都能退出_唯一的家長要先處理其他成員():
    out = _run_leave_flow()
    assert out["childLeave"]["left"] and out["parentLeave"]["left"]
    assert out["lastParent"] and out["lastParent"]["status"] == 409


def test_點了才長出來的東西_打開和收起都有動畫():
    """使用者要的是往下拉開、往上收回，兩個方向都要。

    ⚠️ 只用 CSS 做不到收起：hidden 一設下去元素就消失，沒有時間播動畫。
    所以收起一律走 slideClose（先播完再藏），不能直接寫 el.hidden = true。
    """
    app = read("frontend/js/app.js")
    assert "function slideOpen(el)" in app and "function slideClose(el, done)" in app

    def body(name):
        mo = re.search(r"function %s\([^)]*\) \{(.*?)\n  \}" % name, app, re.S)
        assert mo, "找不到 " + name
        return mo.group(1)

    assert "slideClose(wrap)" in body("foldToggle") and "slideOpen(wrap)" in body("foldToggle")
    assert "slideAway(" in body("ledgerToggle") and "slideOpen(" in body("ledgerToggle")
    assert "slideOpen(p)" in body("acctMenu") and "slideClose(p)" in body("acctMenu"), \
        "帳號選單要往下拉開、往上收回"
    for bad in ("gp.hidden = !gp.hidden", "gp2.hidden = true", "sd.hidden = !sd.hidden",
                "sd2.hidden = true", "mp.hidden = !mp.hidden", "mp2.hidden = true", "wrap.hidden = !on"):
        assert bad not in app, "還有直接瞬間開關的寫法：" + bad

    notify = read("frontend/js/notify.js")
    assert "__slide.close(panel" in notify, "通知面板收起沒有動畫"

    docs = read("frontend/docs/docs.js")
    assert "closing" in docs and "d.animate(" in docs, "文件的 <details> 收起沒有動畫"
    assert "docs.js" in read("frontend/docs/guide.html"), "使用說明沒有載入 docs.js"

    assert "prefers-reduced-motion" in app and "prefers-reduced-motion" in docs, \
        "使用者關掉動態效果時要尊重"


# ===========================================================================
# 換膚：主題就是一組變數
# ===========================================================================

def _css_blocks(css, selector_re):
    """把 `選擇器 { --a: #xxx; ... }` 裡的色碼變數讀成 dict。"""
    out = {}
    for m in re.finditer(selector_re + r"\s*\{(.*?)\n\}", css, re.S):
        body = m.group(m.lastindex)
        key = m.group(1) if m.lastindex > 1 else ":root"
        out[key] = dict(re.findall(r"--([a-z0-9-]+):\s*(#[0-9A-Fa-f]{6})\s*;", body))
    return out


def _contrast(a, b):
    def lum(h):
        h = h.lstrip("#")
        rgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
    la, lb = lum(a), lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def _themes():
    css = read("frontend/css/themes.css")
    return _css_blocks(css, r'\n\[data-theme="([a-z]+)"\]')


def test_主題清單三邊一致():
    """data.js 的清單、themes.css 的區塊、後端的驗證清單，三邊要一模一樣。

    少一邊會發生什麼：
      · data.js 有、CSS 沒有  → 選了之後畫面沒變，使用者以為壞了
      · 前端有、後端沒有      → 按下去先換了，存檔被 422 打回來又換回去
      · 後端有、前端沒有      → 資料庫裡的值前端不認得，登入後退回米白
    """
    import importlib
    import sys as _sys
    _sys.path.insert(0, os.path.join(REPO, "backend"))
    theme = importlib.import_module("app.toolkit.theme")

    data = read("frontend/js/data.js")
    block = data[data.index("  themes: ["):data.index("  ],", data.index("  themes: ["))]
    in_data = re.findall(r"id: '([a-z]+)'", block)
    in_css = list(_themes().keys())

    assert in_data == list(theme.THEMES), "data.js 與 toolkit/theme.py 的主題清單不一致"
    assert in_css == in_data, "themes.css 的 [data-theme] 區塊跟 data.js 對不上：%s / %s" % (in_css, in_data)
    assert theme.DEFAULT == in_data[0] == "paper"
    assert "font:" not in block, "主題只換顏色和形狀，不換字——全站同一套字"


def test_預設主題寫兩次要一樣():
    """米白寫在 tokens.css 的 :root，themes.css 又寫一次給預覽用。兩邊一改漏一邊，預覽就跟實際不一樣。"""
    root = _css_blocks(read("frontend/css/tokens.css"), r"\n:root")
    merged = {}
    for d in root.values():
        merged.update(d)
    paper = _themes()["paper"]
    diff = {k: (merged[k], v) for k, v in paper.items() if k in merged and merged[k].upper() != v.upper()}
    assert not diff, "tokens.css 與 themes.css 的米白不一樣：%s" % diff


RULES = [
    ("ink", "card", 7), ("ink", "paper", 7), ("ink-soft", "card", 4.5), ("ink-soft", "card-2", 4.5),
    ("ink-faint", "card", 4.5), ("ink-faint", "paper", 4.5), ("ink-faint", "card-2", 4.5), ("ink-dim", "card", 3),
    ("accent", "card", 4.5), ("accent", "paper", 4.5), ("on-accent", "accent", 4.5), ("accent-hi", "accent-wash", 4.5),
    ("up", "card", 4.5), ("down", "card", 4.5), ("warn-ink", "card", 4.5), ("warn", "card", 3), ("info", "card", 4.5),
    ("up", "up-wash", 4.5), ("down", "down-wash", 4.5), ("warn-ink", "warn-wash", 4.5),
    ("stack-ink", "stack-1", 4.5), ("stack-ink", "stack-2", 4.5), ("ink", "stack-3", 7), ("ink-faint", "stack-3", 4.5),
    ("ink", "band", 7), ("ink-faint", "band", 4.5), ("badge-ink", "badge", 3.5),
]


def test_每一套主題的字都看得清楚():
    """換膚最容易出事的地方是對比：少女、可愛這種淺色系，字最容易消失在底色裡。

    門檻照 WCAG：主要文字 7:1、次要與小字 4.5:1、圖示與分類色點 3:1。
    ⚠️ 加新主題或調色之前先跑這支。
    """
    bad = []
    for tid, t in _themes().items():
        t = dict(t)
        t.setdefault("badge-ink", "#FFFFFF")
        for fg, bg, th in RULES:
            assert fg in t and bg in t, "%s 少了 --%s 或 --%s" % (tid, fg, bg)
            v = _contrast(t[fg], t[bg])
            if v < th:
                bad.append("%s：--%s 在 --%s 上 %.2f（要 %s）" % (tid, fg, bg, v, th))
        for k, v in t.items():
            if k.startswith(("cat-", "book-")) and _contrast(v, t["card"]) < 3:
                bad.append("%s：--%s 在卡片上 %.2f（要 3）" % (tid, k, _contrast(v, t["card"])))
    assert not bad, "\n".join(bad)


def test_元件只准用變數_不寫死顏色與直角():
    """換膚 = 換變數。元件裡只要寫死一個 #fff，那一塊在深色主題就會變成一塊白板。

    直角也一樣：以前全部寫 border-radius: 0，換成圓潤的主題時那些地方還是方的。
    """
    css = re.sub(r"/\*.*?\*/", "", read("frontend/css/app.css"), flags=re.S)
    hexes = [h for h in re.findall(r"#[0-9A-Fa-f]{3,8}\b", css) if h.lower() != "#000"]
    assert not hexes, "app.css 還有寫死的顏色：%s" % sorted(set(hexes))
    assert "rgba(" not in css and "rgb(" not in css, "app.css 還有寫死的 rgba()"
    zero = re.findall(r"([^{}]*)\{[^}]*border-radius:\s*0\s*[;}]", css)
    allowed = {".seg__b"}
    stray = [z.strip() for z in zero if z.strip() not in allowed]
    assert not stray, "這些還是寫死的直角：%s" % stray
    px = re.findall(r"border-radius:\s*\d+px", css)
    assert not px, "圓角要用 var(--r-*)：%s" % px


def test_會引用別的變數的變數_每個主題都要重算():
    """自訂屬性往下繼承的是算好的值。主題預覽自己掛 data-theme，
    陰影、底紋如果只在 :root 算一次，預覽裡就還是米白的陰影。"""
    tokens = read("frontend/css/tokens.css")
    assert ":root, [data-theme] {" in tokens
    block = tokens[tokens.index(":root, [data-theme] {"):]
    block = block[:block.index("\n}")]
    for v in ("--shadow-card", "--bg-art", "--band-bg", "--scrim"):
        assert v + ":" in block, v + " 要放在 :root, [data-theme] 裡"


def test_主題設定_按下去就換_存不起來就換回去():
    app = read("frontend/js/app.js")
    cards = re.search(r"function themeCards\(cur\) \{(.*?)\n  \}", app, re.S).group(1)
    assert 'data-theme="\' + esc(t.id)' in cards, "預覽要自己掛 data-theme，才看得到那一套真正的樣子"
    choose = re.search(r"function chooseTheme\(id\) \{(.*?)\n  \}", app, re.S).group(1)
    assert choose.index("applyTheme(id)") < choose.index("API.updateProfile({ theme: id })"), "要先換再存，不要讓人等"
    assert "applyTheme(prev)" in choose, "存失敗要換回原本的主題"
    who = re.search(r"function paintWho\(\) \{(.*?)\n  \}", app, re.S).group(1)
    assert "applyTheme(m.user.theme)" in who, "登入之後要以帳號存的主題為準"

    html = read("frontend/index.html")
    head = html[:html.index("</head>")]
    assert head.index("fambudget.theme") < head.index("css/tokens.css"), "主題要在 CSS 載入前掛上，不然重新整理會閃一下"
    assert head.index("css/app.css") < head.index("css/themes.css"), "themes.css 要最後載，才蓋得過元件的結構規則"


_THEME_DRIVER = r"""
const [dataJs, apiJs] = process.argv.slice(2);
const store = new Map();
global.localStorage = { getItem: k => store.has(k) ? store.get(k) : null, setItem: (k, v) => store.set(k, String(v)), removeItem: k => store.delete(k) };
global.document = { querySelector: () => null };
global.setTimeout = fn => setImmediate(fn);
function boot() {
  delete require.cache[require.resolve(dataJs)];
  delete require.cache[require.resolve(apiJs)];
  global.window = {};
  require(dataJs); require(apiJs);
  return window.API;
}
async function fails(p) { try { await p; return null; } catch (e) { return { msg: e.message, status: e.status || null }; } }
(async () => {
  const out = {}, PW = 'password123';
  let API = boot();
  await API.login({ email: 'jianguo@lin.tw', password: PW });
  out.before = (await API.me()).user.theme;
  out.saved = (await API.updateProfile({ theme: 'sky' })).theme;
  out.me = (await API.me()).user.theme;
  out.bad = await fails(API.updateProfile({ theme: 'dark' }));
  out.stillSky = (await API.me()).user.theme;
  await API.login({ email: 'shufen@lin.tw', password: PW });
  out.spouse = (await API.me()).user.theme;
  API = boot();
  await API.login({ email: 'jianguo@lin.tw', password: PW });
  out.afterReload = (await API.me()).user.theme;
  process.stdout.write(JSON.stringify(out));
})().catch(e => { console.error(e); process.exit(1); });
"""


def test_主題存在帳號上_各選各的():
    import json
    import shutil
    import subprocess
    import tempfile

    if not shutil.which("node"):
        pytest.skip("這台機器沒有 node")
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
        fh.write(_THEME_DRIVER)
        tmp = fh.name
    res = subprocess.run(
        ["node", tmp, os.path.join(REPO, "frontend", "js", "data.js"),
         os.path.join(REPO, "frontend", "js", "api.js")], capture_output=True)
    assert res.returncode == 0, res.stderr.decode("utf-8", "replace")
    out = json.loads(res.stdout.decode("utf-8"))
    assert out["before"] == "paper", "沒選過主題的人，契約說 theme 一定有值（paper）"
    assert out["saved"] == out["me"] == "sky"
    assert out["bad"] and out["bad"]["status"] == 422, "清單外的主題要回 422"
    assert out["stillSky"] == "sky", "被擋掉的請求不可以改到原本的主題"
    assert out["spouse"] == "paper", "主題是個人的，家人不會跟著換"
    assert out["afterReload"] == "sky", "重新整理之後主題不見了"


def test_總覽照銀行_App_疊卡_常用功能_底部分頁():
    """參考富邦新版：數字卡疊在一起、常用功能收在一張卡裡、手機底部分頁中間是記一筆。"""
    app = read("frontend/js/app.js")
    home = re.search(r"function vHome\(\) \{(.*?)\n  \}", app, re.S).group(1)
    for part in ("wal__strip--1", "wal__strip--2", "wal__card", 'class="qk"', 'class="dgrid"'):
        assert part in home, "總覽少了 " + part
    assert "hero" not in home, "舊的大數字卡還在"

    html = read("frontend/index.html")
    bar = html[html.index('<nav class="tabbar"'):html.index("</nav>", html.index('<nav class="tabbar"'))]
    for tab in ('data-tab=""', 'data-tab="entry"', 'data-tab="stats"', 'data-tab="advice"', 'data-quick="entry"'):
        assert tab in bar, "底部分頁少了 " + tab
    css = read("frontend/css/app.css")
    assert "body.is-admin .tabbar" in css and "body.is-out .tabbar" in css, "平台管理員與還沒登入不該有底部分頁"


# ===========================================================================
# 總覽：今天的紀錄 ／ 右上角：我的帳戶卡
# ===========================================================================

def test_總覽最下面是今天的紀錄_只看不改():
    """使用者要的是「一打開 App 就看得到今天的記帳動向」。

    ⚠️ 只放今天，不是把收支明細搬過來：沒有篩選、沒有刪除、沒有表格。
    """
    app = read("frontend/js/app.js")
    home = re.search(r"function vHome\(\) \{(.*?)\n  \}", app, re.S).group(1)
    assert "from: todayKey(), to: todayKey()" in home, "今天的紀錄要用日期範圍去問，不是拿全部回來自己挑"
    assert home.rindex("todayCard(") > home.index("預算使用狀況"), "今天的紀錄放在最下面"
    card = re.search(r"function todayCard\(rows, fam\) \{(.*?)\n  \}", app, re.S).group(1)
    for bad in ("data-del", "<input", "<select", "txTable("):
        assert bad not in card, "今天的紀錄只看不改，不該有 " + bad
    assert "fam ? '' : '<div class=\"tdy__go\">" in card, "全家模式沒有記帳，空的時候也不放記一筆"

    key = re.search(r"function todayKey\(\) \{(.*?)\n  \}", app, re.S).group(1)
    assert "API.mode !== 'http'" in key and "meta.updated" in key, \
        "mock 的今天要跟示範資料同一天，不然今天的紀錄永遠是空的"


def test_帳戶卡不再重複儀表板上的功能():
    """右上角點開原本是一串連結，跟常用功能幾乎一樣。

    現在放的是儀表板上沒有的：這個月記帳天數、家人、快速換主題。
    進個人資料和家庭成員是點「名字」和「家人那一列」，不另外列成選項。
    """
    html = read("frontend/index.html")
    menu = html[html.index('id="acctPanel"'):html.index("</header>")]
    for label in ("收支明細", "帳本", "統計", "財務建議", ">個人資料<", ">家庭成員<"):
        assert label not in menu, "帳戶卡又列出了儀表板上已經有的：" + label
    assert len(re.findall(r'data-nav="', menu)) <= 2
    for part in ('id="acctHabit"', 'id="acctFam"', 'id="acctThemes"'):
        assert part in menu, "帳戶卡少了 " + part

    app = read("frontend/js/app.js")
    paint = re.search(r"function paintAcct\(\) \{(.*?)\n  \}", app, re.S).group(1)
    assert "data-theme-pick" in paint and 'data-theme="' in paint, "主題小圓點要能直接換，而且自己掛著那一套的顏色"
    assert "isPlatformAdmin" in paint, "平台管理員沒有帳也沒有家庭，不要去問"
    mark = re.search(r"function markTheme\(id\) \{(.*?)\n  \}", app, re.S).group(1)
    assert ".acctm__sw" in mark, "在帳戶卡換主題之後，設定頁的「使用中」也要跟著變（反過來也是）"
    menu_fn = re.search(r"function acctMenu\(on\) \{(.*?)\n  \}", app, re.S).group(1)
    assert "paintAcct()" in menu_fn, "打開的時候才去問資料，不要每一頁都先算好"


_TXF_DRIVER = _THEME_DRIVER.split("(async () => {")[0] + r"""
(async () => {
  const out = {}, PW = 'password123';
  const API = boot();
  await API.login({ email: 'jianguo@lin.tw', password: PW });
  const all = (await API.transactions({ userId: 'U1' })).transactions;
  const day = (await API.transactions({ userId: 'U1', from: '2026-09-10', to: '2026-09-10' })).transactions;
  const range = (await API.transactions({ userId: 'U1', from: '2026-09-03', to: '2026-09-05' })).transactions;
  const none = (await API.transactions({ userId: 'U1', from: '2026-09-11', to: '2026-09-01' })).transactions;
  const cat = all[0].cat;
  const byCat = (await API.transactions({ userId: 'U1', categoryId: cat })).transactions;
  out.allN = all.length;
  out.dayDates = [...new Set(day.map(t => t.date))];
  out.dayN = day.length;
  out.rangeOk = range.length > 0 && range.every(t => t.date >= '2026-09-03' && t.date <= '2026-09-05');
  out.rangeHasEnds = range.some(t => t.date === '2026-09-03') && range.some(t => t.date === '2026-09-05');
  out.noneN = none.length;
  out.catOk = byCat.length > 0 && byCat.every(t => t.cat === cat) && byCat.length < all.length;
  out.sorted = all.every((t, i) => i === 0 || all[i - 1].date >= t.date);
  process.stdout.write(JSON.stringify(out));
})().catch(e => { console.error(e); process.exit(1); });
"""


def test_明細的日期與分類篩選真的有篩():
    """⚠️ from／to／categoryId 早就寫在契約和白名單裡，mock 卻沒有真的篩——
    傳了等於沒傳，在 mock 下完全看不出來。「今天的紀錄」要靠它，所以補上並釘住。"""
    import json
    import shutil
    import subprocess
    import tempfile

    if not shutil.which("node"):
        pytest.skip("這台機器沒有 node")
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
        fh.write(_TXF_DRIVER)
        tmp = fh.name
    res = subprocess.run(
        ["node", tmp, os.path.join(REPO, "frontend", "js", "data.js"),
         os.path.join(REPO, "frontend", "js", "api.js")], capture_output=True)
    assert res.returncode == 0, res.stderr.decode("utf-8", "replace")
    out = json.loads(res.stdout.decode("utf-8"))
    assert out["dayDates"] == ["2026-09-10"] and out["dayN"] < out["allN"], "from=to 只該回那一天"
    assert out["rangeOk"] and out["rangeHasEnds"], "日期範圍兩端都要包含"
    assert out["noneN"] == 0
    assert out["catOk"], "categoryId 沒有篩"
    assert out["sorted"], "明細要新的在前"


# ===========================================================================
# 品牌與文件：跟系統同一套樣子
# ===========================================================================

DOC_PAGES = ("index", "fastapi", "restful", "files", "api", "model", "guide")


def test_品牌是上下兩行的藝術字():
    """使用者要的品牌：上面「家庭記帳」、下面草寫英文，英文比較小、兩行一樣寬、沒有框。

    ⚠️ 以前是方塊裡一個「帳」字（老土），後來是膠囊框裡的草寫英文（不要框）。
    中文也要藝術字：Google Fonts 上的中文毛筆字多半只有簡體，沒有「記」「帳」，
    所以用日文字型裡的毛筆字 Yuji Boku（這四個字都有）。
    """
    lockup = '<span class="brand__zh">家庭記帳</span><span class="brand__en" aria-hidden="true">FamBudget</span>'
    html = read("frontend/index.html")
    assert lockup in html, "系統頂列的品牌不是上下兩行"
    assert "brand__m" not in html and ">帳</span>" not in html
    assert "family=Yuji+Boku" in html and "family=Kaushan+Script" in html, "品牌字體沒有載入"
    assert "text=%E5%AE%B6%E5%BA%AD%E8%A8%98%E5%B8%B3FamBudget" in html, "品牌字只需要這幾個字，用 text= 只載這幾個字"
    assert lockup in read("frontend/js/app.js"), "登入頁的品牌沒有換"
    for pg in DOC_PAGES:
        page = read("frontend/docs/%s.html" % pg)
        assert lockup in page, pg + " 的品牌沒有換成上下兩行"
        assert "rail__mark" not in page and "g-mark" not in page

    tokens = read("frontend/css/tokens.css")
    en = re.search(r"\.brand__en \{([^}]*)\}", tokens).group(1)
    assert "font-size: .856em" in en, "英文要比中文小，而且縮到跟中文一樣寬（量出來的比例 0.856）"
    for bad in ("border", "background", "border-radius", "padding"):
        assert bad + ":" not in en, "英文不要框：.brand__en 不該有 " + bad


def test_全站同一套字():
    """以前一頁裡混了襯線標題、黑體內文、等寬數字，主題還會各自換字。

    現在全站只有粉圓體；例外是品牌那兩行（藝術字）和程式碼（要對齊，一定等寬）。
    字體名稱只准出現在 tokens.css，其他地方一律寫 var(--sans)／var(--code)。
    """
    tokens = read("frontend/css/tokens.css")
    assert re.search(r'--sans: "Huninn"', tokens)
    for alias in ("--serif", "--display", "--mono"):
        assert "%s: var(--sans);" % alias in tokens, alias + " 要跟 --sans 同一套"
    assert "code, pre, kbd, samp { font-family: var(--code); }" in tokens

    themes = re.sub(r"/\*.*?\*/", "", read("frontend/css/themes.css"), flags=re.S)
    assert "font-family" not in themes and not re.search(r"--(sans|serif|display|mono):", themes), "主題不換字"

    named = re.compile(r'font-family:(?!\s*(?:var\(|inherit))[^;}]*')
    for f in ("frontend/css/app.css", "frontend/docs/docs.css"):
        css = re.sub(r"/\*.*?\*/", "", read(f), flags=re.S)
        assert not named.findall(css), "%s 直接寫了字體名稱：%s" % (f, named.findall(css)[:3])
    for pg in DOC_PAGES:
        page = read("frontend/docs/%s.html" % pg)
        assert not named.findall(page), "%s 直接寫了字體名稱" % pg
        assert "Noto+Sans+TC" not in page and "Noto+Serif+TC" not in page, pg + " 還在載舊的字體"
    assert "Noto+Sans+TC" not in read("frontend/index.html")
    assert "function loadFont(" not in read("frontend/js/app.js"), "主題不換字，不需要另外載字"


def test_文件跟系統同一套主題與樣子():
    """文件跟產品長得不一樣，讀者從系統點過來會以為進了另一個網站。

    現在每一頁都載系統的 tokens.css ＋ themes.css，在系統選的主題文件也跟著換；
    所以文件裡不准寫死顏色——寫死的那一塊在深色主題就會變成一塊白板。
    """
    data = read("frontend/js/data.js")
    block = data[data.index("  themes: ["):data.index("  ],", data.index("  themes: ["))]
    css = read("frontend/docs/docs.css")
    assert not re.findall(r"#[0-9A-Fa-f]{3,8}\b|rgba?\(", re.sub(r"/\*.*?\*/", "", css, flags=re.S)), \
        "docs.css 還有寫死的顏色"
    for pg in DOC_PAGES:
        page = read("frontend/docs/%s.html" % pg)
        head = page[:page.index("</head>")]
        assert "../css/tokens.css" in head and "../css/themes.css" in head, pg + " 沒有載系統的樣式"
        assert head.index("fambudget.theme") < head.index("../css/tokens.css"), pg + " 主題要在樣式載入前掛上"
        body = re.sub(r"<!--.*?-->", "", page, flags=re.S)
        stray = re.findall(r"#[0-9A-Fa-f]{6}\b|rgba\(", body)
        assert not stray, "%s 還有寫死的顏色：%s" % (pg, sorted(set(stray))[:5])


def test_專題文件每一頁先講重點():
    """文件很長，第一次讀的人要先知道這一頁在講什麼：開頭一張「這一頁的重點」。"""
    for pg in ("index", "fastapi", "restful", "files", "api", "model"):
        page = read("frontend/docs/%s.html" % pg)
        m = re.search(r'<section class="kp".*?<ul class="kp__l">(.*?)</ul>', page, re.S)
        assert m, pg + " 沒有重點卡"
        items = re.findall(r"<li><b>[^<]+</b><span>[^<]+</span></li>", m.group(1))
        assert 4 <= len(items) <= 7, "%s 的重點要 4～7 條，現在 %d 條" % (pg, len(items))
        kp_at = page.index('class="kp"')
        assert kp_at > page.index("</header>"), pg + " 重點卡要放在開場後面"
        if 'class="sec' in page:
            assert kp_at < page.index('class="sec'), pg + " 重點卡要放在第一節前面"
    css = read("frontend/docs/docs.css")
    assert "content: '重點'" in css, "每一節的導言要標出「重點」"
