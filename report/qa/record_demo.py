"""完整流程的示範影片（10/27 版）：在部署好的網站上，從一個空帳號開始走一遍，逐格擷取畫面、疊上中文字幕，合成 MP4。

    python report/qa/record_demo.py                     → 線上站錄影，產出 report/qa/家庭記帳_完整流程.mp4
    python report/qa/record_demo.py --trial             → 試跑：不錄影，每一步存一張截圖到 report/qa/trial/（快很多）
    python report/qa/record_demo.py --target local ...  → 本機（localhost:5195 前端 ＋ 127.0.0.1:8010 後端）

跑的時候在終端機問兩個帳號（密碼用 getpass：不顯示、不存檔，影片裡的密碼欄只看得到圓點）：
    家長  名字、一個「還沒註冊過」的 email、密碼 → 影片裡現場註冊
    子女  事先註冊好、點過驗證信、還沒加入家庭的空帳號的 email 與密碼
    小技巧：Gmail 可以用「名字+任意字@gmail.com」，信都寄到同一個信箱，不用另外開信箱。
註冊之後到信箱打開驗證信，把信裡的連結貼回終端機；等信的這段不錄，影片從「點了驗證信」接著錄。

流程：未登入首頁 → 註冊 → 驗證信 → 個人化設定 → 導覽 → 個人總覽（固定收入自動入帳）→ 段落記帳 → 總覽下方面板
     → 建立活動（說明、開始日／結束日）→ 預先規劃 → 活動設定與目標金額 → 邀請朋友 → 活動總覽與活動記帳
     → 建立家庭、邀請子女 → 子女加入家庭與活動（設定只能看）→ 零用金自動記帳 → 子女的鈴鐺 → 統計、財務建議
     → 刪除要輸入密碼（只拍到對話框）→ 手機版

⚠️ 會在網站上留下資料：兩個帳號、一個家庭、兩個活動、幾筆帳與零用金。錄完可以到「個人資料 › 刪除帳號」刪掉。
⚠️ 刪除的動作只拍到「輸入密碼」的對話框就按取消，不真的刪。
⚠️ --accounts（把帳密寫在 JSON 檔）只給本機試跑用，線上一律在終端機輸入。
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import datetime as dt
import getpass
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

import httpx
import websockets
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
TARGETS = {
    "live": ("https://fambudget-web.onrender.com", "https://fambudget-backend-tdvg.onrender.com",
             "LIVE · fambudget-web.onrender.com"),
    # 用 IPv4：無頭 Chrome 會把 localhost 先解析成 IPv6，本機後端只聽 IPv4
    "local": ("http://localhost:5195", "http://127.0.0.1:8010", "LOCAL · 本機"),
}
CHROME = [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
          r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"]
W, H = 1280, 800
TW = dt.timezone(dt.timedelta(hours=8))

CAPTION_JS = r"""
(function (step, total, title, desc, where) {
  var id = 'qa-cap', el = document.getElementById(id);
  if (!el) {
    el = document.createElement('div'); el.id = id;
    el.setAttribute('style', [
      'position:fixed', 'left:0', 'right:0', 'bottom:0', 'z-index:2147483647', 'pointer-events:none',
      'background:rgba(11,15,20,.92)', 'border-top:2px solid #0ABAB5', 'color:#e6edf3',
      'font-family:"Microsoft JhengHei","Noto Sans TC",sans-serif', 'padding:14px 28px 16px',
      'display:flex', 'flex-wrap:wrap', 'gap:4px 18px', 'align-items:baseline'].join(';'));
    document.documentElement.appendChild(el);
  }
  var small = innerWidth < 600;
  el.style.padding = small ? '10px 14px 12px' : '14px 28px 16px';
  el.innerHTML = '<span style="font:700 ' + (small ? 12 : 15) + 'px Consolas,monospace;color:#0ABAB5;white-space:nowrap">' + step + ' / ' + total + '</span>' +
    '<span style="font-size:' + (small ? 17 : 21) + 'px;font-weight:700;white-space:nowrap">' + title + '</span>' +
    '<span style="font-size:' + (small ? 13 : 15) + 'px;color:#a9b6c3">' + desc + '</span>';
})
"""

#: 畫面上的滑鼠游標。無頭 Chrome 錄不到真的游標，所以畫一個：
#: 從上一個位置滑到目標（0.8 秒）→ 停一下 → 點的地方出現波紋 → 才真的點下去，看的人跟得上。
#: sel 是 CSS 選擇器；寫成 "text:開始使用" 是找畫面上有這幾個字的按鈕或連結。sel 是 null 時只把游標放回上次的位置（換頁之後）。
CURSOR_JS = r"""
(async function (sel, x0, y0, pause, doClick) {
  var sleep = function (ms) { return new Promise(function (r) { setTimeout(r, ms); }); };
  var cur = document.getElementById('qa-cur');
  if (!cur) {
    cur = document.createElement('div'); cur.id = 'qa-cur';
    cur.innerHTML = '<svg viewBox="0 0 24 24" width="28" height="28"><path d="M2 1.5l7.8 20 2.7-8.1 8-2.8z" ' +
      'fill="#fff" stroke="#111" stroke-width="1.6" stroke-linejoin="round"/></svg>';
    cur.setAttribute('style', 'position:fixed;left:0;top:0;width:28px;height:28px;z-index:2147483647;pointer-events:none;' +
      'filter:drop-shadow(0 2px 3px rgba(0,0,0,.45));transition:transform .8s cubic-bezier(.45,0,.25,1);' +
      'transform:translate(' + (x0 - 2) + 'px,' + (y0 - 2) + 'px)');
    document.documentElement.appendChild(cur);
    await sleep(60);
  }
  if (!sel) return [x0, y0];
  var el = null;
  if (sel.indexOf('text:') === 0) {
    var want = sel.slice(5);
    el = Array.prototype.filter.call(document.querySelectorAll('a,button,label,summary,[data-nav],[data-quick]'),
      function (e) { return e.offsetParent !== null && e.textContent.trim().indexOf(want) >= 0; })[0];
  } else {
    el = document.querySelector(sel);
  }
  if (!el) return null;
  var r = el.getBoundingClientRect();
  if (r.top < 70 || r.bottom > innerHeight - 100) {
    el.scrollIntoView({ block: 'center', behavior: 'smooth' });
    await sleep(750);
    r = el.getBoundingClientRect();
  }
  var x = Math.round(r.left + Math.min(r.width / 2, 70)), y = Math.round(r.top + r.height / 2);
  cur.style.transform = 'translate(' + (x - 2) + 'px,' + (y - 2) + 'px)';
  await sleep(850);
  await sleep(pause * 1000);
  if (doClick) {
    var rip = document.createElement('div');
    rip.setAttribute('style', 'position:fixed;left:' + (x - 20) + 'px;top:' + (y - 20) + 'px;width:40px;height:40px;' +
      'border:3px solid #2BFFE0;border-radius:50%;z-index:2147483646;pointer-events:none');
    document.documentElement.appendChild(rip);
    rip.animate([{ transform: 'scale(.3)', opacity: 1 }, { transform: 'scale(1.5)', opacity: 0 }], { duration: 500 });
    setTimeout(function () { rip.remove(); }, 520);
    await sleep(180);
    el.click();
  }
  return [x, y];
})
"""

CARD_CSS = """
html,body{margin:0;height:100%;background:#0b0f14;color:#e6edf3;font-family:"Microsoft JhengHei","Noto Sans TC",sans-serif}
body{background-image:linear-gradient(#1f2a36 1px,transparent 1px),linear-gradient(90deg,#1f2a36 1px,transparent 1px);background-size:48px 48px}
.c{position:absolute;inset:0;display:flex;flex-direction:column;justify-content:center;padding:0 110px}
.e{color:#0ABAB5;font:14px Consolas,monospace;letter-spacing:.2em}
h1{font-size:54px;margin:18px 0 12px;color:#fff;line-height:1.2}
p{color:#a9b6c3;font-size:20px;margin:0 0 8px}
.k{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-top:34px}
.k div{border:1px solid #1f2a36;border-top:2px solid #0ABAB5;background:rgba(17,24,33,.92);padding:16px 18px}
.k b{display:block;font:700 30px Consolas,monospace;color:#fff}.k span{color:#a9b6c3;font-size:15px}
"""


def card_html(eyebrow, title, lines, kpis=()):
    k = "".join("<div><b>%s</b><span>%s</span></div>" % kv for kv in kpis)
    return ("<!doctype html><html><head><meta charset='utf-8'><style>%s</style></head><body><div class='c'>"
            "<div class='e'>%s</div><h1>%s</h1>%s%s</div></body></html>") % (
        CARD_CSS, eyebrow, title, "".join("<p>%s</p>" % x for x in lines), "<div class='k'>%s</div>" % k if k else "")


class CDP:
    def __init__(self, ws):
        self.ws, self.seq, self.wait, self.frames = ws, 0, {}, []
        self.recording = False
        self.ff = []          # [(開始, 結束, 合成後最多幾秒)]：等載入、等模型的片段，合成時快轉
        self.errors = []      # 頁面上的 JavaScript 錯誤：卡住的時候印出來

    async def reader(self):
        async for raw in self.ws:
            msg = json.loads(raw)
            if msg.get("method") == "Page.screencastFrame":
                p = msg["params"]
                if self.recording:
                    self.frames.append((p["metadata"]["timestamp"], base64.b64decode(p["data"])))
                self.seq += 1
                await self.ws.send(json.dumps({"id": self.seq, "method": "Page.screencastFrameAck",
                                               "params": {"sessionId": p["sessionId"]}}))
            elif msg.get("method") == "Runtime.exceptionThrown":
                d = msg["params"]["exceptionDetails"]
                self.errors.append((d.get("exception") or {}).get("description") or d.get("text"))
            elif "id" in msg and msg["id"] in self.wait:
                self.wait.pop(msg["id"]).set_result(msg)

    async def send(self, method, **params):
        self.seq += 1
        me = self.seq
        fut = asyncio.get_event_loop().create_future()
        self.wait[me] = fut
        await self.ws.send(json.dumps({"id": me, "method": method, "params": params}))
        msg = await asyncio.wait_for(fut, 60)
        if "error" in msg:
            raise RuntimeError("%s: %s" % (method, msg["error"]))
        return msg.get("result", {})

    async def js(self, expr, wait=False):
        r = await self.send("Runtime.evaluate", expression=expr, awaitPromise=wait, returnByValue=True)
        return r.get("result", {}).get("value")


def jwt_sub(token):
    """權杖的 sub 就是使用者 id（只讀，不驗簽）"""
    return str(json.loads(base64.urlsafe_b64decode(token.split(".")[1] + "==="))["sub"])


def api_login(api, acc):
    """子女帳號用 API 登入拿權杖（不在畫面上打密碼）；沒走完個人化設定的先標成走完，一登入才不會被帶去設定頁。"""
    r = httpx.post(api + "/api/auth/login", json={"email": acc["email"], "password": acc["password"]}, timeout=90)
    if r.status_code != 200:
        raise SystemExit("子女帳號登入失敗（%s）：%s" % (r.status_code, r.text[:200]))
    d = r.json()
    tok = {k: d[k] for k in ("accessToken", "refreshToken", "expiresIn")}
    tok["savedAt"] = int(time.time() * 1000)
    h = {"authorization": "Bearer " + d["accessToken"]}
    me = httpx.get(api + "/api/auth/me", headers=h, timeout=60).json()
    if me.get("family"):
        raise SystemExit("子女帳號已經在一個家庭裡了：影片要示範「邀請子女加入新家庭」，請換一個還沒加入家庭的帳號")
    if not me["user"].get("onboardedAt"):
        httpx.patch(api + "/api/auth/me", headers=h, json={"onboarded": True}, timeout=60)
    return tok, jwt_sub(d["accessToken"]), me["user"].get("name") or "子女"


async def run(ws_url, args, accounts, workdir):
    front, api, tag = TARGETS[args.target]
    local = args.target == "local"
    no_model = local and not args.ai              # 本機沒接模型：AI 那兩步字幕照實說是規則備援
    trial = args.trial
    pace = 0.3 if trial else 1.0
    parent, kid = accounts["parent"], accounts["kid"]
    kid_tok, kid_id, kid_name = api_login(api, kid)
    today = dt.datetime.now(TW).date()
    trip_end = today + dt.timedelta(days=4)
    party = dt.date(today.year, 12, 31)
    if party <= today + dt.timedelta(days=1):
        party = today + dt.timedelta(days=30)
    trial_dir = os.path.join(HERE, "trial")
    if trial:
        shutil.rmtree(trial_dir, ignore_errors=True)
        os.makedirs(trial_dir)

    async with websockets.connect(ws_url, max_size=256 * 1024 * 1024) as ws:
        c = CDP(ws)
        reader = asyncio.ensure_future(c.reader())
        await c.send("Page.enable")
        await c.send("Runtime.enable")
        dsf = 2 if args.snaps else 1
        await c.send("Emulation.setDeviceMetricsOverride", width=W, height=H, deviceScaleFactor=dsf, mobile=False)
        # 步驟數＝這支腳本裡呼叫 cap() 的次數（以前寫死，加步驟忘了改就會出現 26 / 24）
        total = io.open(__file__, encoding="utf-8").read().count("await " + "cap(")
        pos = [W // 2, H // 2]
        step = [0]
        shown = {}
        ids = {}

        async def wait(sec):
            await asyncio.sleep(sec * pace)

        async def recap():
            # 換頁（重新載入）會把字幕清掉：每次換頁後立刻補上目前這一步的字幕
            if shown:
                await c.js("(%s)(%d, %d, %s, %s, %s)" % (CAPTION_JS, step[0], total, json.dumps(shown["title"]),
                                                         json.dumps(shown["desc"]), json.dumps(tag)))

        snap_dir = os.path.join(os.path.dirname(HERE), "assets", "demo")
        if args.snaps:
            shutil.rmtree(snap_dir, ignore_errors=True)
            os.makedirs(snap_dir)

        marks = {}

        async def snap(name, spots=None):
            """專案報告用：先把字幕、游標藏起來，等畫面停好再拍，拍完放回去。
            spots：要在簡報上標 ①②③ 的元件（CSS 選擇器，或 "js:" 開頭的運算式），
            記下它們在畫面上的位置（佔寬、高的比例）到 marks.json，簡報照這個位置畫編號，不用目測"""
            if not args.snaps:
                return
            await c.js("['qa-cap','qa-cur'].forEach(function (i) { var e = document.getElementById(i); if (e) e.style.visibility = 'hidden'; })")
            await asyncio.sleep(0.8)
            if spots:
                marks[name] = await c.js("""(function (specs) { return specs.map(function (sp) {
                    var e = sp.indexOf('js:') === 0 ? eval(sp.slice(3)) : document.querySelector(sp);
                    if (!e) return null;
                    var r = e.getBoundingClientRect();
                    if (r.bottom < 0 || r.top > innerHeight || r.width === 0) return null;
                    return [Math.max(0, r.left) / innerWidth, (r.top + Math.min(r.height, 56) / 2) / innerHeight];
                  }); })(%s)""" % json.dumps(spots))
                with open(os.path.join(snap_dir, "marks.json"), "w", encoding="utf-8") as f:
                    json.dump(marks, f, ensure_ascii=False, indent=1)
            shot = await c.send("Page.captureScreenshot", format="png")
            with open(os.path.join(snap_dir, name + ".png"), "wb") as f:
                f.write(base64.b64decode(shot["data"]))
            await c.js("['qa-cap','qa-cur'].forEach(function (i) { var e = document.getElementById(i); if (e) e.style.visibility = ''; })")

        # 這幾步一出字幕就是要的畫面：直接拍。後面的清單是簡報上要標編號的元件
        SNAP_AT = {
            "首頁": ("landing", None),
            "理財習慣": ("finance", None),
            "主題": ("theme", None),
            "個人總覽": ("home", ['[data-flt="income"]', '[data-flt="expense"]', ".wal__v", ".wal__meta", ".qk", ".hpanel"]),
            "解析結果": ("parse", [".btbl__raw", '.btbl__r [data-b="date"]', '.btbl__r [data-b="amount"]', '.btbl__r [data-b="cat"]',
                               "js:[...document.querySelectorAll('.btbl__r [data-b=merchant]')].pop()", "#paraSave"]),
            "今天的紀錄": ("today", None),
            "建立活動": ("create", None),
            "預先規劃": ("planned", None),
            "活動的設定": ("settings", None),
            "邀請朋友": ("invite_friend", None),
            "活動記帳": ("activity", [".act__note", ".act__f dt:nth-of-type(2)", ".act__goal", '[data-flt="expense"]',
                                  "[data-personal-return]", ".hpanel"]),
            "邀請家人": ("family", None),
            "子女收到邀請": ("kid_invite", None),
            "成員只能看": ("kid_readonly", None),
            "照看子女": ("guardian", None),
            "零用金": ("allowance_form", None),
            "零用金自動記帳": ("allowance", None),
            "子女的鈴鐺": ("kid_bell", None),
            "統計": ("stats", None),
            "刪除要輸入密碼": ("danger", None),
            "手機版": ("mobile", None),
        }

        async def cap(title, desc):
            step[0] += 1
            shown.update(title=title, desc=desc)
            await recap()
            if title in SNAP_AT:
                await snap(*SNAP_AT[title])
            print("  %2d/%d %s" % (step[0], total, title), flush=True)
            if trial:
                await asyncio.sleep(0.4)
                shot = await c.send("Page.captureScreenshot", format="png")
                with open(os.path.join(trial_dir, "%02d_%s.png" % (step[0], title.replace("/", "／"))), "wb") as f:
                    f.write(base64.b64decode(shot["data"]))

        async def click(sel, pause=0.6, do=True, need=True):
            """游標移過去、停一下、波紋、點下去。找不到：need=True 就停下來說是哪一步，不然跳過。"""
            r = await c.js("(%s)(%s, %d, %d, %s, %s)" % (CURSOR_JS, json.dumps(sel), pos[0], pos[1], pause * pace,
                                                          "true" if do else "false"), wait=True)
            if isinstance(r, (list, tuple)) and len(r) == 2:
                pos[0], pos[1] = int(r[0]), int(r[1])
            if r is None and need:
                raise RuntimeError("畫面上找不到要點的東西：%s（第 %d 步「%s」）" % (sel, step[0], shown.get("title", "")))
            return r is not None

        async def point():
            # 換頁之後游標會被清掉：放回上次的位置，不要突然消失
            await c.js("(%s)(null, %d, %d, 0, false)" % (CURSOR_JS, pos[0], pos[1]), wait=True)

        async def until(expr, timeout=40, need=True):
            # ⚠️ 一定要先轉成 true／false：querySelector 傳回來的 DOM 元素在 Python 這邊會變成空物件 {}
            t0 = time.time()
            while time.time() - t0 < timeout:
                if await c.js("!!(%s)" % expr):
                    return True
                await asyncio.sleep(0.4)
            if need:
                # 停下來之前留一張截圖和畫面上的提示訊息，才知道卡在哪
                shot = await c.send("Page.captureScreenshot", format="png")
                with open(os.path.join(HERE, "record_fail.png"), "wb") as f:
                    f.write(base64.b64decode(shot["data"]))
                toasts = await c.js("[...document.querySelectorAll('.toast')].map(x => x.textContent).join(' ／ ')")
                raise RuntimeError("等不到畫面：%s（第 %d 步「%s」）畫面提示：%s；頁面錯誤：%s；截圖 report/qa/record_fail.png"
                                   % (expr, step[0], shown.get("title", ""), toasts, c.errors[-3:]))
            return False

        async def go(url, ready=None, keep=1.0, timeout=60):
            # 從換頁到畫面準備好的這一段快轉成最多 keep 秒
            t0 = time.time()
            await c.send("Page.navigate", url=url)
            await asyncio.sleep(0.6)
            await recap()
            if ready:
                await until(ready, timeout)
            else:
                await asyncio.sleep(1.5)
            await recap()
            if not url.startswith("file:"):
                await point()
            c.ff.append((t0, time.time(), keep))

        async def page(hash_, ready, keep=1.0):
            await go(front + "/?r=%d%s" % (time.time() * 1000, hash_), ready, keep)

        async def busy(expr, keep=1.5, timeout=60):
            """等後端或模型做完：這一段快轉"""
            t0 = time.time()
            await until(expr, timeout)
            c.ff.append((t0, time.time(), keep))
            await recap()

        async def type_in(sel, text, delay=75):
            await c.js("""(async (s, t, d) => { const el = document.querySelector(s); el.focus(); el.value = '';
                          for (const ch of t) { el.value += ch; el.dispatchEvent(new Event('input', {bubbles: true}));
                          await new Promise(r => setTimeout(r, d)); } })(%s, %s, %d)"""
                       % (json.dumps(sel), json.dumps(text), int(delay * pace)), wait=True)

        async def set_val(sel, value, change=True):
            await c.js("""(function (s, v, ch) { var e = document.querySelector(s); e.value = v;
                          e.dispatchEvent(new Event('input', {bubbles: true}));
                          if (ch) e.dispatchEvent(new Event('change', {bubbles: true})); })(%s, %s, %s)"""
                       % (json.dumps(sel), json.dumps(value), "true" if change else "false"))

        async def scroll_to(sel, block="center"):
            await c.js("var e=document.querySelector(%s); if(e) e.scrollIntoView({block:%s, behavior:'smooth'})"
                       % (json.dumps(sel), json.dumps(block)))
            await asyncio.sleep(0.8)

        async def use(tok, uid, tour_done=True):
            # 換人：權杖放進 localStorage（跟前端登入後存的一樣）；導覽標成看過，一進總覽才不會先問要不要導覽
            await c.js("localStorage.setItem('fambudget.auth', %s)" % json.dumps(tok if isinstance(tok, str) else json.dumps(tok)))
            if tour_done:
                await c.js("localStorage.setItem(%s, 'done')" % json.dumps("fambudget.tour." + str(uid)))

        async def para(text):
            """記一筆 → 段落記帳 → 打一段話 → 解析 → 等結果"""
            await click('[data-quick="entry"]')
            await until("document.querySelector('[data-mode=\"para\"]') || document.querySelector('textarea')", 30)
            if await c.js("!!(document.querySelector('[data-mode=\"para\"]') && !document.querySelector('[data-mode=\"para\"]').classList.contains('on'))"):
                await click('[data-mode="para"]')
            await until("document.querySelector('textarea')", 30)
            await recap()
            await click("textarea", pause=0.3)
            await c.js("""(async (t, d) => { const ta = document.querySelector('textarea'); ta.focus(); ta.value = '';
                          for (const ch of t) { ta.value += ch; ta.dispatchEvent(new Event('input', {bubbles: true}));
                          await new Promise(r => setTimeout(r, d)); } })(%s, %d)""" % (json.dumps(text), int(80 * pace)), wait=True)
            await wait(0.8)
            await click("#paraGo")
            await busy("document.getElementById('paraSave')", keep=2.5, timeout=90)
            # 接了 AI 卻偶爾逾時（畫面寫「AI 暫時沒有回應」、改用規則）：重新解析，最多再試兩次
            for _ in range(2 if args.ai else 0):
                if not await c.js("document.body.innerText.includes('AI 暫時沒有回應')"):
                    break
                t0 = time.time()
                await click("#paraGo", pause=0.2)
                await asyncio.sleep(1.5)
                await until("document.getElementById('paraSave') && !document.getElementById('paraGo').disabled", 90)
                c.ff.append((t0, time.time(), 1.0))
            await wait(0.8)
            await scroll_to(".btbl, #paraSave")

        def card_url(name, html):
            path = os.path.join(workdir, name + ".html")
            with io.open(path, "w", encoding="utf-8") as f:
                f.write(html)
            return "file:///" + path.replace("\\", "/")

        # ---------------------------------------------------------------- 片頭（不算步驟）
        await go(card_url("open", card_html("FAMBUDGET · FULL WALKTHROUGH · " + today.isoformat(), "家庭記帳<br>從一個空帳號開始",
                                            ["註冊 → 個人化設定 → 記帳 → 活動 → 家庭與零用金 → 統計與建議 → 手機版",
                                             ("全程在部署好的網站上操作" if not local else
                                              "在本機錄：跟線上同一份程式；本機沒有接模型，AI 那兩步用規則備援" if no_model else
                                              "在本機錄：跟線上同一份程式、同一個 AI 模型（Claude）"),
                                             "每一步下方的字幕說明正在做什麼；需要密碼的動作只拍到對話框"])), keep=0.5)
        if not trial:
            await c.send("Page.startScreencast", format="jpeg", quality=82, maxWidth=W, maxHeight=H, everyNthFrame=1)
            c.recording = True
        await wait(4)

        # ---------------------------------------------------------------- 1. 註冊
        await go(front + "/docs/guide.html", keep=0.1)
        await c.js("localStorage.removeItem('fambudget.auth')" + ("; localStorage.setItem('fambudget.api', %s)" % json.dumps(api) if local else ""))
        await go(front + "/?r=%d#/login" % (time.time() * 1000), "document.body.innerText.includes('開始使用')")
        await cap("首頁", "還沒登入時先說清楚這個系統能做什麼")
        await wait(3.5)
        await click("text:開始使用")
        await until("document.querySelector('[data-gate=\"register\"]')", 15)
        await wait(1)
        await click('[data-gate="register"]')
        await until("document.getElementById('rgName')", 15)
        await cap("註冊", "只要名字、email、密碼")
        await click("#rgName", pause=0.3)
        await type_in("#rgName", parent["name"])
        await click("#rgEmail", pause=0.2)
        await type_in("#rgEmail", parent["email"], 55)
        # 密碼一次填好，畫面上只看得到圓點；這支腳本不存密碼
        await click("#rgPw", pause=0.2)
        await set_val("#rgPw", parent["password"], change=False)
        await wait(1)
        await snap("register")
        await click("#regF button[type=submit]")
        ok = await until("document.getElementById('regNote')", 30, need=False)
        if not ok:
            msg = await c.js("[...document.querySelectorAll('.toast')].map(x=>x.textContent).join(' ')")
            raise SystemExit("註冊沒有成功：%s（這個 email 可能已經註冊過了，換一個沒用過的）" % msg)
        await wait(0.6)
        await cap("去收信", "註冊完不會直接登入：請他去收信，email 已經填好")
        await wait(4.5)

        # ---------------------------------------------------------------- 2. 驗證信 → 個人化設定
        c.recording = False                                    # 等信的這段不錄
        t_pause = time.time()
        if local:
            # 本機寄不出信：帳號直接算驗證過（docs/02「寄不出信的環境」），用 API 登入代替點信
            r = httpx.post(api + "/api/auth/login", json={"email": parent["email"], "password": parent["password"]}, timeout=60).json()
            tok = {k: r[k] for k in ("accessToken", "refreshToken", "expiresIn")}
            tok["savedAt"] = int(time.time() * 1000)
            await use(tok, jwt_sub(r["accessToken"]), tour_done=False)
            link = front + "/?r=%d#/" % (time.time() * 1000)
        else:
            print("\n>>> 到信箱打開「確認你的家庭記帳 email」那封信，把信裡按鈕的連結貼在這裡（整串網址）：", flush=True)
            link = (await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)).strip()
            if "#/verify/" not in link:
                raise SystemExit("這不是驗證信的連結（要有 #/verify/）")
        c.recording = not trial
        c.ff.append((t_pause, time.time(), 0.3))              # 等信的空檔：合成時壓成一瞬間
        await go(link, "document.getElementById('suGoalF')", keep=0.8)
        await cap("點了驗證信", "第一次點就直接登入、接著做個人化設定：收入怎麼來、每個月想存多少")
        await wait(2.5)
        await click('label:has(input[name="suType"][value="salary"])')
        await until("document.getElementById('suAmt')", 10)
        await wait(0.6)
        await click("#suAmt", pause=0.3)
        await type_in("#suAmt", "32000", 110)
        await click("#suDay", pause=0.3, do=False)
        await set_val("#suDay", "5")
        await wait(0.8)
        await click('[data-su-goal="5000"]')
        await wait(1.5)
        await snap("setup")
        await click("#suGoalF button[type=submit]")
        await until("document.getElementById('suFinF')", 30)
        await cap("理財習慣", "選像自己的就好，財務建議會參考；可以跳過")
        await wait(1.5)
        await click("#suFinF label.pick", pause=0.4)
        await click("#suFinF label.pick--sm", pause=0.4)
        await wait(1)
        await click("#suFinF button[type=submit]")
        await until("document.getElementById('thmRow')", 30)
        await cap("主題", "按一下整個系統就換成那個樣子；存在帳號上，換裝置也一樣")
        await wait(1.2)
        await click('[data-theme-pick="sky"]')
        await wait(2)
        await click('[data-su-done="finish"]')
        await until("document.getElementById('tourYes') || document.querySelector('.wal__card')", 30)

        # ---------------------------------------------------------------- 3. 導覽與個人總覽
        # 「第一次用？」是總覽畫好之後才跳出來的：多等幾秒
        if await until("document.getElementById('tourYes')", 8, need=False):
            await cap("新手導覽", "第一次進來會問要不要導覽，照畫面上看得到的東西帶一遍")
            await wait(2)
            await click("#tourYes")
            await until("document.getElementById('tourNext')", 10)
            await wait(1)
            await snap("tour")
            for _ in range(3):
                await wait(1.6)
                await click("#tourNext", pause=0.3, need=False)
            await wait(1.2)
            await click("#tourSkip", need=False)
            await wait(1)
        parent_uid = await c.js("JSON.parse(localStorage.getItem('fambudget.auth')).accessToken.split('.')[1]")
        parent_uid = str(json.loads(base64.urlsafe_b64decode(parent_uid + "==="))["sub"])
        await c.js("localStorage.setItem(%s, 'done')" % json.dumps("fambudget.tour." + parent_uid))
        await page("#/", "document.querySelector('.wal__card') && document.querySelector('.hpanel')")
        await cap("個人總覽", "月薪設了每月 5 號入帳：這個月的已經自動記一筆。還可以花 ＝ 收入 − 每月想存")
        await wait(5)

        # ---------------------------------------------------------------- 4. 段落記帳與總覽下方面板
        await cap("段落記帳", "一句話記好幾筆：直接打一段平常講話的句子")
        await para("早餐蛋餅 45，捷運 30，午餐便當 95，晚上全聯買牙膏 89")
        await cap("解析結果", "本機沒有接模型：先用規則把一段話拆成四筆、分好類；一樣要人確認才存" if no_model
                  else "AI 把一段話拆成四筆，日期、金額、分類都填好；看過、確認才會存")
        await wait(6)
        await click("#paraSave")
        await busy("!document.getElementById('paraSave')", keep=1.2)
        await page("#/", "document.querySelector('.hpanel .txr')")
        await scroll_to(".hpanel", "end")
        await point()
        await cap("今天的紀錄", "儀表板下方是分頁面板：第一頁是今天的紀錄，格式跟明細一樣，可以直接改、刪；內容在面板裡捲動")
        await wait(3)
        await c.js("var s=document.querySelector('.hpanel__scroll'); if(s) s.scrollTo({top: 400, behavior: 'smooth'})")
        await wait(2)
        await click('[data-hptab="budget"]')
        await wait(2.5)
        await click('[data-hptab="today"]')
        await wait(1.5)

        # ---------------------------------------------------------------- 5. 活動
        await page("#/groups", "document.querySelector('[data-fold=\"gnew\"]')")
        await cap("活動管理", "活動是個人底下的小帳本：旅行、搬家、聚餐，各有自己的總覽")
        await wait(2.5)
        await click('[data-fold="gnew"]')
        await until("document.getElementById('gnName')", 10)
        await click("#gnName", pause=0.3)
        await type_in("#gnName", "沖繩畢業旅行", 90)
        await click("#gnNote", pause=0.3)
        await type_in("#gnNote", "四天三夜，機票住宿都記在這裡", 70)
        await click("#gnEnd", pause=0.3, do=False)
        await set_val("#gnEnd", trip_end.isoformat())
        await cap("建立活動", "開始日預設今天、可以自己選；結束日不能比今天早，也不能比開始日早")
        await wait(4)
        await click("#gnewF button[type=submit]")
        await busy("[...document.querySelectorAll('.lg__t')].some(e => e.textContent === '沖繩畢業旅行')")
        await wait(1.5)
        await click('[data-fold="gnew"]')
        await until("document.getElementById('gnName')", 10)
        await click("#gnName", pause=0.3)
        await type_in("#gnName", "跨年聚餐", 90)
        await click("#gnNote", pause=0.3)
        await type_in("#gnNote", "全家一起吃火鍋", 70)
        await click("#gnStart", pause=0.3, do=False)
        await set_val("#gnStart", party.isoformat())
        await click("#gnEnd", pause=0.3, do=False)
        await set_val("#gnEnd", party.isoformat())
        await wait(1)
        await click("#gnewF button[type=submit]")
        await busy("document.querySelector('[data-fold=\"gplan\"]')")
        await scroll_to('[data-fold="gplan"]')
        await point()
        await cap("預先規劃", "開始日訂在以後：先放在「預先規劃」、不進活動選單；到了那天自動放上去並通知成員")
        await wait(4)
        await click("#gswBtn")
        await wait(2.5)
        await snap("dropdown")
        await click("#gswBtn")
        await wait(0.8)

        ids["trip"] = await c.js("([...document.querySelectorAll('.lg')].find(x => (x.querySelector('.lg__t')||{}).textContent === '沖繩畢業旅行')||{dataset:{}}).dataset.lgid")
        trip = ids["trip"]
        if not trip:
            raise RuntimeError("找不到剛建立的活動")
        await click('.lg[data-lgid="%s"] .lg__h' % trip)
        await until("document.querySelector('[data-gname=\"%s\"]')" % trip, 10)
        await cap("活動的設定", "名稱、說明、開始日、結束日、顏色、目標金額建立後都能改——只有建立者能改")
        await wait(3)
        await click('[data-gopen="%s"]' % trip)
        await until("document.querySelector('[data-ggoal=\"%s\"]')" % trip, 10)
        await type_in('[data-ggoal="%s"]' % trip, "20000", 110)
        await set_val('[data-ggoal="%s"]' % trip, "20000")
        await wait(2.5)
        await click('.lg[data-lgid="%s"] details.activity-invite-panel summary' % trip)
        await wait(0.8)
        sel = 'form[data-activity-find="%s"] input[name=email]' % trip
        await click(sel, pause=0.3)
        await type_in(sel, kid["email"], 45)
        await click('form[data-activity-find="%s"] button[type=submit]' % trip)
        await busy("document.querySelector('[data-activity-send=\"%s\"]')" % trip, keep=1)
        await cap("邀請朋友", "用完整的 email 找到人才送出；也可以產生只能用一次的邀請碼")
        await wait(2)
        await click('[data-activity-send="%s"]' % trip)
        await wait(3)

        await click("#gswBtn")
        await wait(1.2)
        await click('.gsw__i[data-group="%s"]' % trip)
        await wait(1)
        await page("#/", "document.querySelector('.act__f')")
        await cap("活動總覽", "主卡是「這個活動是什麼」：說明、期間、成員、筆數、目標金額；上面兩條照樣是收入、支出")
        await wait(5)
        await para("機票 8200，民宿訂金 3000")
        await wait(2)
        await click("#paraSave")
        await busy("!document.getElementById('paraSave')", keep=1.2)
        await page("#/", "document.querySelector('.act__f')")
        await cap("活動記帳", "記在活動裡的帳只算在活動；目標金額寫明比的是累計支出還是結餘")
        await wait(5)
        await click("[data-personal-return]")
        await wait(2)

        # ---------------------------------------------------------------- 6. 家庭
        await page("#/members", "document.getElementById('famNewF')")
        await cap("建立家庭", "建立的人是家長；可以順便填全家的長期存款目標")
        await click("#famName", pause=0.3)
        await type_in("#famName", "王家", 120)
        await click("#famGoalNote", pause=0.3)
        await type_in("#famGoalNote", "全家出國基金", 70)
        await set_val("#famGoalAmount", "300000")
        await wait(1)
        await click("#famNewF button[type=submit]")
        await busy("document.querySelector('[data-fold=\"finv\"]')")
        await wait(1.5)
        await click('[data-fold="finv"]')
        await until("document.getElementById('invEmail')", 10)
        await click("#invEmail", pause=0.3)
        await type_in("#invEmail", kid["email"], 45)
        await click("#invFindF button[type=submit]")
        await busy("document.querySelector('[data-inv-send]')", keep=1)
        await click('[data-invrole="child"]', need=False)
        await cap("邀請家人", "找到人之後選身分（子女／家長）再送出，對方的鈴鐺會馬上收到")
        await wait(2)
        await click("[data-inv-send]")
        await wait(3)
        parent_auth = await c.js("localStorage.getItem('fambudget.auth')")

        # ---------------------------------------------------------------- 7. 子女
        await use(kid_tok, kid_id)
        await page("#/", "document.querySelector('[data-inv-accept]')")
        await cap("子女收到邀請", "換成子女的帳號：總覽最上面就是家庭邀請，按「加入」就進這個家庭")
        await wait(4)
        await click("[data-inv-accept]")
        # 偶爾（本機 SQLite）加入成功了畫面卻沒重畫：等 12 秒還沒變就重新整理，不讓整支影片卡住
        t0 = time.time()
        if not await until("!document.querySelector('[data-inv-accept]')", 12, need=False):
            await page("#/", "document.querySelector('.wal__card') && !document.querySelector('[data-inv-accept]')")
        c.ff.append((t0, time.time(), 1.5))
        await wait(1.5)
        await page("#/groups", "document.querySelector('[data-activity-response$=\"|accept\"]')")
        await wait(1)
        await snap("kid_activity_invite")
        await click('[data-activity-response$="|accept"]')
        await busy("document.querySelector('.lg[data-lgid=\"%s\"]')" % trip, keep=1.5)
        await click('.lg[data-lgid="%s"] .lg__h' % trip)
        await until("document.querySelector('.lg[data-lgid=\"%s\"] .lg__ro')" % trip, 10)
        await cap("成員只能看", "加入活動之後看得到說明、期間、建立者訂的目標金額，但不能改")
        await wait(5)

        # ---------------------------------------------------------------- 8. 零用金
        await use(parent_auth, parent_uid)
        await page("#/members", "document.querySelector('[data-gs-start=\"%s\"]')" % kid_id)
        await scroll_to('[data-gs-start="%s"]' % kid_id)
        await point()
        await cap("照看子女", "子女加入之後，家長按「開始照看」才看得到他的帳、才能給零用金；子女看得到是誰在照看")
        await wait(2.5)
        await click('[data-gs-start="%s"]' % kid_id)
        await busy("[...document.querySelectorAll('.toast')].some(t => t.textContent.includes('開始照看'))", keep=1)
        await wait(2)
        await page("#/member/%s" % kid_id, "document.querySelector('[data-allow]')")
        await cap("零用金", "家長照看子女：每月零用金和發放日；改完離開欄位就存")
        await wait(2)
        await click("[data-allow]", pause=0.3)
        await type_in("[data-allow]", "1500", 120)
        await set_val("[data-allow]", "1500")
        await busy("[...document.querySelectorAll('.toast')].some(t => t.textContent.includes('號給'))", keep=1.5)
        await wait(2)
        await cap("零用金自動記帳", "到了發放日自動記一對帳：家長一筆支出、孩子一筆收入，並通知孩子")
        await scroll_to(".txw, .txt", "start")
        await wait(4)

        await use(kid_tok, kid_id)
        await page("#/", "document.querySelector('.wal__card')")
        await wait(1)
        await click("#bell")
        await until("document.querySelector('.bell__del, .bell__i, .bell li')", 15)
        await cap("子女的鈴鐺", "家庭邀請、零用金入帳都即時進鈴鐺；零用金算在子女這個月可以花的錢裡")
        await wait(5)
        await click("#bell")
        await wait(1)

        # ---------------------------------------------------------------- 9. 統計與建議
        await use(parent_auth, parent_uid)
        await page("#/stats", "document.querySelector('.donut, svg circle, .dt, .chart')")
        await cap("統計", "收支對照、錢花在哪：數字跟總覽、明細同一個來源")
        await wait(5)
        await page("#/advice", "document.getElementById('advGen')")
        await cap("財務建議", "數字由資料庫先算好；本機沒接模型，就用同一批數字整理成建議，每個數字都附算式" if no_model
                  else "數字由資料庫先算好，AI 只把它寫成好懂的建議；每個數字都附算式，找得到出處")
        await wait(1.5)
        await click("#advGen")
        await wait(2)
        await busy("document.getElementById('advGen') && !document.getElementById('advGen').disabled", keep=3, timeout=120)
        for _ in range(2 if args.ai else 0):                   # 同上：AI 偶爾逾時就再產生一次
            if not await c.js("document.body.innerText.includes('AI 暫時沒有回應')"):
                break
            t0 = time.time()
            await click("#advGen", pause=0.2)
            await asyncio.sleep(2)
            await until("document.getElementById('advGen') && !document.getElementById('advGen').disabled", 120)
            c.ff.append((t0, time.time(), 1.5))
        await click(".ad__h", need=False)
        await wait(5)
        await snap("advice", [".ad__lv", ".ad__t", ".ad__b", ".ad__k", "js:document.querySelectorAll('.ad__k')[1]", "#advGen"])

        # ---------------------------------------------------------------- 10. 刪除要密碼
        await page("#/", "document.querySelector('.hpanel [data-del]')")
        await scroll_to(".hpanel", "end")
        await click(".hpanel [data-del]")
        await until("document.getElementById('dgPw')", 10)
        await cap("刪除要輸入密碼", "刪掉就救不回來：要輸入自己的密碼確認（示範到這裡，按取消）")
        await wait(4)
        await click("#dgNo")
        await wait(1)

        # ---------------------------------------------------------------- 11. 手機版
        await c.send("Emulation.setDeviceMetricsOverride", width=375, height=812, deviceScaleFactor=dsf, mobile=True)
        if not trial:
            await c.send("Page.stopScreencast")
            await c.send("Page.startScreencast", format="jpeg", quality=82, maxWidth=375, maxHeight=812, everyNthFrame=1)
        await page("#/", "document.querySelector('.wal__card')")
        await cap("手機版", "底部分頁列；總覽、面板、表格都照手機寬度重排，沒有左右捲動")
        await wait(3)
        await c.js("window.scrollTo({top: 900, behavior: 'smooth'})")
        await wait(4)
        await snap("mobile2")
        await c.js("localStorage.removeItem('fambudget.auth')")

        # ---------------------------------------------------------------- 片尾
        if not trial:
            await c.send("Page.stopScreencast")
        await c.send("Emulation.setDeviceMetricsOverride", width=W, height=H, deviceScaleFactor=1, mobile=False)
        if not trial:
            await c.send("Page.startScreencast", format="jpeg", quality=82, maxWidth=W, maxHeight=H, everyNthFrame=1)
        shown.clear()
        await go(card_url("end", card_html("END", "謝謝觀看", [
            "個人、活動、家庭三種視角，同一套記帳"])), keep=0.5)
        await wait(5)
        c.recording = False
        if not trial:
            await c.send("Page.stopScreencast")
        reader.cancel()
        return c.frames, c.ff


def remap(ff):
    """原本的時間 → 合成後的時間：快轉片段壓到 keep 秒，其他照原速。"""
    segs = sorted((a, b, min(1.0, k / (b - a)) if b > a else 1.0) for a, b, k in ff)

    def f(t):
        cut = 0.0
        for a, b, factor in segs:
            if t <= a:
                break
            cut += (min(t, b) - a) * (1 - factor)
        return t - cut
    return f


def encode(frames, out_mp4, workdir, ff=()):
    import imageio_ffmpeg
    frames.sort(key=lambda f: f[0])
    tmap = remap(ff)
    lines = []
    for i, (ts, data) in enumerate(frames):
        img = Image.open(io.BytesIO(data)).convert("RGB")
        if img.size != (W, H):                        # 手機畫面：放在深色畫布正中間
            scale = H / img.size[1]
            img = img.resize((max(1, int(img.size[0] * scale)), H))
            canvas = Image.new("RGB", (W, H), (11, 15, 20))
            canvas.paste(img, ((W - img.size[0]) // 2, 0))
            img = canvas
        path = os.path.join(workdir, "f%05d.jpg" % i)
        img.save(path, quality=90)
        nxt = frames[i + 1][0] if i + 1 < len(frames) else ts + 1.5
        lines.append("file '%s'\nduration %.3f" % (path.replace("\\", "/"), max(0.001, tmap(nxt) - tmap(ts))))
    lines.append("file '%s'" % os.path.join(workdir, "f%05d.jpg" % (len(frames) - 1)).replace("\\", "/"))
    lst = os.path.join(workdir, "list.txt")
    with io.open(lst, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-f", "concat", "-safe", "0", "-i", lst,
                    "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-crf", "21", "-preset", "medium",
                    "-movflags", "+faststart", out_mp4], check=True, capture_output=True)



def ask_accounts(args):
    if args.accounts:
        if args.target != "local":
            raise SystemExit("--accounts 只給本機試跑用；線上請在終端機輸入帳密")
        with io.open(args.accounts, encoding="utf-8") as f:
            return json.load(f)
    print("影片會在網站上現場註冊一個家長帳號，再邀請一個子女帳號加入家庭與活動。")
    print("密碼不會顯示、不會存檔，影片裡的密碼欄只看得到圓點。\n")
    name = input("家長的名字（影片裡會看到，直接按 Enter 用「王小明」）：").strip() or "王小明"
    email = input("家長的 email（還沒註冊過的，影片裡現場註冊）：").strip()
    pw = getpass.getpass("家長要設的密碼（至少 8 個字）：")
    if len(pw) < 8:
        raise SystemExit("密碼至少 8 個字")
    kid_email = input("子女帳號的 email（事先註冊好、點過驗證信、還沒加入家庭）：").strip()
    kid_pw = getpass.getpass("子女帳號的密碼：")
    if not email or not kid_email or email.lower() == kid_email.lower():
        raise SystemExit("兩個 email 都要填，而且不能一樣")
    return {"parent": {"name": name, "email": email, "password": pw},
            "kid": {"email": kid_email, "password": kid_pw}}


def main() -> int:
    ap = argparse.ArgumentParser(description="家庭記帳完整流程的示範影片")
    ap.add_argument("--target", choices=sorted(TARGETS), default="live")
    ap.add_argument("--trial", action="store_true", help="試跑：不錄影，每一步存一張截圖到 report/qa/trial/")
    ap.add_argument("--accounts", help="（只給本機試跑）帳密的 JSON 檔：{parent: {name, email, password}, kid: {email, password}}")
    ap.add_argument("--show", action="store_true", help="開出 Chrome 視窗（不是無頭），看得到它在做什麼")
    ap.add_argument("--ai", action="store_true",
                    help="本機後端有接 AI 模型（backend/.env 填了 MODEL_PROVIDER 與金鑰）：字幕照實寫 AI，不寫規則備援")
    ap.add_argument("--snaps", action="store_true",
                    help="（配合 --trial）在重點畫面拍乾淨的高解析截圖（不帶字幕、游標）到 report/assets/demo/，專案報告用")
    args = ap.parse_args()
    accounts = ask_accounts(args)
    front, api, _ = TARGETS[args.target]
    # 免費主機閒置會睡：先把後端叫醒
    for _ in range(6):
        try:
            if httpx.get(api + "/openapi.json", timeout=90).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(5)
    exe = next(p for p in CHROME if os.path.exists(p))
    workdir = tempfile.mkdtemp(prefix="fambudget-video-")
    profile = os.path.join(workdir, "profile")
    port = 9335
    flags = ["--remote-debugging-port=%d" % port, "--user-data-dir=" + profile, "--hide-scrollbars",
             "--no-first-run", "--lang=zh-TW", "--window-size=%d,%d" % (W, H)]
    if not args.show:
        flags.insert(0, "--headless=new")
    proc = subprocess.Popen([exe] + flags + ["about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            try:
                tabs = httpx.get("http://127.0.0.1:%d/json/list" % port, timeout=1).json()
                page = next(t for t in tabs if t.get("type") == "page")
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.25)
        frames, ff = asyncio.run(run(page["webSocketDebuggerUrl"], args, accounts, workdir))
        if args.trial:
            print("試跑完成，每一步的截圖在", os.path.join(HERE, "trial"))
            return 0
        print("frames:", len(frames), "seconds:", round(frames[-1][0] - frames[0][0], 1) if frames else 0)
        out = os.path.join(HERE, "家庭記帳_完整流程.mp4")
        encode(frames, out, workdir, ff)
        print(out)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:      # 無頭 Chrome 偶爾關不掉：強制結束
            proc.kill()
        shutil.rmtree(workdir, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
