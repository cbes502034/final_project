"""完整測試流程的示範影片：本機 Chrome（無頭）依序操作線上站，逐格擷取畫面，疊上中文字幕，合成 MP4。

    python report/qa/record_demo.py --tokens <只含 access token 的 JSON>   → report/qa/家庭記帳_測試流程.mp4

tokens 就是 backend/tools/demo_seed.py --tokens 寫出的檔案（本機 http://localhost:8010 的林家 dad、kid 與 admin）。

⚠️ 只帶 30 分鐘就過期的 access token，不帶 refresh token；線上站的畫面上不輸入任何密碼。
⚠️ 未登入的四步在線上站錄（右上角標 LIVE）；登入之後都在本機錄（標 LOCAL）：
   - 新用戶註冊：線上站要建真帳號、要收真的信，所以用本機的示範模式（沒有後端，
     「信」的連結直接放在畫面上），密碼是這次隨機產生的假值；
   - 家長、子女、平台管理：錄影不在畫面上輸入密碼，線上測試帳號的登入失效時改用本機示範的林家。
     本機沒有接模型，AI 那幾步是規則備援（字幕會講）；線上 Claude 的實測結果在測試報告裡。
   要先開本機前端：python -m http.server 5195 --directory frontend（以及 8010 的後端）。
⚠️ 寫入的都是本機的示範資料庫（段落記帳 3 筆、刪一則通知），線上站不會多任何資料。
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import io
import json
import os
import secrets
import shutil
import subprocess
import tempfile
import time

import httpx
import websockets
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
FRONT = "https://fambudget-web.onrender.com"
BACKEND = "https://fambudget-backend-tdvg.onrender.com"
LOCAL = "http://localhost:5195"
LOCAL_API = "http://127.0.0.1:8010"          # 用 IPv4：無頭 Chrome 會把 localhost 先解析成 IPv6，本機後端只聽 IPv4
TAG_LIVE = "LIVE · fambudget-web.onrender.com"
DEMO = "LOCAL · 本機示範資料（林家；同一份程式，本機沒接模型）"
CHROME = [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
          r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"]
W, H = 1280, 800

#: 驗證信實測時的第一封（11:09 寄出、11:12 過期）：拿來示範「過期的連結會被拒絕」
EXPIRED_VERIFY = ("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZW1haWwiOiJjYmVzNTAyMDM0QGdtYWlsLmNvbSIsInR5cGUiOiJ2ZXJp"
                  "ZnlfZW1haWwiLCJpYXQiOjE3OTIzNzkzNjksImV4cCI6MTc5MjM3OTU0OX0.DPhhMJB2BCiYaxjOpP5DOzIAZeAHN7tOXMZu50bA2V8")

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
    var tag = document.createElement('div'); tag.id = 'qa-tag';
    tag.setAttribute('style', 'position:fixed;top:10px;right:12px;z-index:2147483647;pointer-events:none;' +
      'background:rgba(11,15,20,.85);color:#2BFFE0;font:12px Consolas,monospace;padding:4px 10px;border:1px solid #0ABAB5');
    document.documentElement.appendChild(tag);
  }
  document.getElementById('qa-tag').textContent = where;
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


async def run(ws_url, tokens, workdir):
    async with websockets.connect(ws_url, max_size=256 * 1024 * 1024) as ws:
        c = CDP(ws)
        reader = asyncio.ensure_future(c.reader())
        await c.send("Page.enable")
        await c.send("Runtime.enable")
        await c.send("Emulation.setDeviceMetricsOverride", width=W, height=H, deviceScaleFactor=1, mobile=False)
        # 步驟數＝這支腳本裡呼叫 cap() 的次數（以前寫死，加步驟忘了改就會出現 26 / 24）
        total = io.open(__file__, encoding="utf-8").read().count("await " + "cap(")
        pos = [W // 2, H // 2]
        step = [0]
        where = [TAG_LIVE]

        shown = {}

        async def cap(title, desc):
            step[0] += 1
            shown.update(title=title, desc=desc)
            await recap()

        async def recap():
            # 換頁（重新載入）會把字幕清掉：每次換頁後立刻補上目前這一步的字幕
            if shown:
                await c.js("(%s)(%d, %d, %s, %s, %s)" % (CAPTION_JS, step[0], total, json.dumps(shown["title"]),
                                                         json.dumps(shown["desc"]), json.dumps(where[0])))

        async def click(sel, pause=0.6, do=True):
            """游標移過去、停一下、波紋、點下去。找不到就跳過（不讓整支影片停住）。"""
            r = await c.js("(%s)(%s, %d, %d, %s, %s)" % (CURSOR_JS, json.dumps(sel), pos[0], pos[1], pause,
                                                          "true" if do else "false"), wait=True)
            # 點下去如果整頁換掉，回傳值會拿不到（或不是兩個數字）：沿用上一個位置就好
            if isinstance(r, (list, tuple)) and len(r) == 2:
                pos[0], pos[1] = int(r[0]), int(r[1])
            return r is not None

        async def point():
            # 換頁之後游標會被清掉：放回上次的位置，不要突然消失
            await c.js("(%s)(null, %d, %d, 0, false)" % (CURSOR_JS, pos[0], pos[1]), wait=True)

        async def go(url, wait=5.0, ready=None, keep=1.0):
            # 從按下去到畫面準備好的這一段快轉成最多 keep 秒
            t0 = time.time()
            await c.send("Page.navigate", url=url)
            await asyncio.sleep(0.6)
            await recap()
            if ready:
                await until(ready, 45)
            else:
                await asyncio.sleep(max(0.0, wait - 0.6))
            await recap()
            if not url.startswith("file:"):
                await point()
            c.ff.append((t0, time.time(), keep))

        def uid_of(who):
            # 權杖的 sub 就是使用者 id（只讀，不驗簽）
            return json.loads(base64.urlsafe_b64decode(tokens[who]["accessToken"].split(".")[1] + "==="))["sub"]

        async def login(who):
            # 看過導覽記在帳號上（fambudget.tour.<id>）：標成看過，一進總覽才不會先問要不要導覽
            await c.js("localStorage.setItem('fambudget.auth', %s); localStorage.setItem(%s, 'done')"
                       % (json.dumps(json.dumps(tokens[who])), json.dumps("fambudget.tour." + str(uid_of(who)))))

        async def until(expr, timeout=40):
            # ⚠️ 一定要先轉成 true／false：條件常常是 querySelector(...)，DOM 元素傳回來會變成空物件 {}，
            #    在 Python 裡是「否」，每次都要等到逾時（整支影片曾經因此多等了快 10 分鐘）
            t0 = time.time()
            while time.time() - t0 < timeout:
                if await c.js("!!(%s)" % expr):
                    return True
                await asyncio.sleep(0.5)
            return False

        def card_url(name, html):
            path = os.path.join(workdir, name + ".html")
            with io.open(path, "w", encoding="utf-8") as f:
                f.write(html)
            return "file:///" + path.replace("\\", "/")

        # 片頭（不算步驟）
        await go(card_url("open", card_html("FAMBUDGET · QA WALKTHROUGH · 2026-10-22", "家庭記帳<br>完整測試流程",
                                            ["未登入 → 新用戶註冊 → 家長記帳與建議 → 刪除 → 家庭與權限 → 平台管理 → 手機版",
                                             "右上角標 LIVE 是在 Render 正式網站實測；標 LOCAL 是本機示範資料（同一份程式）",
                                             "每一步下方的字幕說明正在驗證什麼"])), 0.5)
        await c.send("Page.startScreencast", format="jpeg", quality=82, maxWidth=W, maxHeight=H, everyNthFrame=1)
        c.recording = True
        await asyncio.sleep(4)

        # ---------- 未登入 ----------
        await go(FRONT + "/docs/guide.html", 1.5, keep=0.1)
        await c.js("localStorage.removeItem('fambudget.auth')")
        await go(FRONT + "/?r=%d#/login" % (time.time() * 1000), ready="document.body.innerText.includes('開始使用')")
        await cap("首頁", "還沒登入時，先說清楚這個系統能做什麼")
        await asyncio.sleep(4)
        await click("text:開始使用")
        await asyncio.sleep(1.5)
        await cap("登入", "測試帳號已經登入過；影片用登入後的狀態，不在畫面上輸入密碼")
        await asyncio.sleep(3.5)
        step[0] += 1
        shown.update(title="忘記密碼", desc="輸入 email → Brevo 寄出 30 分鐘有效的重設連結（實測收得到）")
        await go(FRONT + "/#/forgot", ready="document.querySelector('#fgEmail')")
        step[0] -= 1
        await cap("忘記密碼", "輸入 email → Brevo 寄出 30 分鐘有效的重設連結（實測收得到）")
        await asyncio.sleep(3.5)
        step[0] += 1
        shown.update(title="過期的驗證連結", desc="這封驗證信 11:12 就過期了：連結被拒絕，網址上的權杖也被拿掉")
        await go(FRONT + "/?r=%d#/verify/%s" % (time.time() * 1000, EXPIRED_VERIFY),
                 ready="document.body.innerText.includes('過期') || document.body.innerText.includes('無效')")
        step[0] -= 1
        await cap("過期的驗證連結", "這封驗證信 11:12 就過期了：連結被拒絕，網址上的權杖也被拿掉")
        await asyncio.sleep(5)

        # ---------- 新用戶（本機示範：沒有寄信，信的連結直接放在畫面上） ----------
        where[0] = "LOCAL · 本機示範：沒有寄信，信的連結放在畫面上"
        step[0] += 1
        shown.update(title="註冊", desc="只要名字、email、密碼")
        await go(LOCAL + "/?api=&r=%d#/register" % (time.time() * 1000), ready="document.getElementById('rgName')")
        step[0] -= 1
        await cap("註冊", "只要名字、email、密碼；建好之後寄一封確認信")
        await click("#rgName", pause=0.3)
        await c.js("""(async (n, m) => { const t = async (id, v) => { const el = document.getElementById(id); el.focus();
                      for (const ch of v) { el.value += ch; await new Promise(r => setTimeout(r, 70)); } };
                      await t('rgName', n); await t('rgEmail', m); })(%s, %s)""" % (
            json.dumps("林小安"), json.dumps("xiaoan.demo@example.com")), wait=True)
        # 密碼是這次隨機產生的假值（本機示範模式，不是任何真帳號），一次填好，畫面上只看得到圓點
        await click("#rgPw", pause=0.2)
        await c.js("document.getElementById('rgPw').value = %s" % json.dumps("Demo-" + secrets.token_hex(5)))
        await asyncio.sleep(1.2)
        await click("#regF button[type=submit]")
        await until("document.getElementById('regNote')", 15)
        await asyncio.sleep(0.6)
        await cap("去收信", "註冊完不會直接登入：回到登入頁請他去收信，email 已經填好")
        await asyncio.sleep(5)
        await click("#regNote a")
        await until("document.getElementById('suGoal')", 15)
        await asyncio.sleep(0.8)
        await recap()
        await cap("點了驗證信", "第一次點就直接登入、接著做個人化設定；沒驗證的人進不了這一頁")
        await asyncio.sleep(2.5)
        await click('[data-su-goal="5000"]')
        await asyncio.sleep(1.8)
        await click("#suGoalF button[type=submit]")
        await until("document.getElementById('suFinF') || document.getElementById('thmRow')", 15)
        await asyncio.sleep(2.5)
        await click("[data-su-done]")
        await until("document.getElementById('tourYes')", 15)
        await asyncio.sleep(1.2)
        await cap("新手導覽", "第一次進來會問要不要導覽，照畫面上看得到的東西帶一遍")
        await asyncio.sleep(2.5)
        await click("#tourYes")
        await until("document.getElementById('tourNext')", 10)
        for _ in range(8):
            await asyncio.sleep(1.4)
            last = await c.js("var n=document.getElementById('tourNext'); n?n.textContent:''")
            await click("#tourNext", pause=0.3)
            if last != "下一步":
                break
        await asyncio.sleep(1.5)
        where[0] = TAG_LIVE

        # ---------- 家長（本機示範資料：林家三口、近三個月的帳） ----------
        where[0] = DEMO
        step[0] += 1
        shown.update(title="家長總覽", desc="換成家長的帳號")
        await go(LOCAL + "/docs/guide.html", 1.5, keep=0.1)
        await c.js("localStorage.setItem('fambudget.api', %s)" % json.dumps(LOCAL_API))
        await login("dad")
        await go(LOCAL + "/?r=%d#/" % (time.time() * 1000), ready="document.querySelector('.wal__v') && document.querySelector('.bcard')")
        await asyncio.sleep(1)
        step[0] -= 1
        await cap("家長總覽", "這個月還可以花多少＝收入－每月想存；各分類預算用了幾成，超過的標紅")
        await asyncio.sleep(5)

        await click('[data-flt="income"]')
        await until("document.querySelector('.fchip') && document.querySelector('#txList .txr')", 20)
        await recap()
        await point()
        await cap("本月收入", "點「本月收入」就只看這個月的收入（點支出就只看支出）；「本月」標籤按 ✕ 看全部")
        await asyncio.sleep(4)
        await go(LOCAL + "/#/", ready="document.querySelector('.wal__v') && document.querySelector('[data-quick=\"entry\"]')")

        await cap("段落記帳", "一句話記好幾筆：直接打一段平常講話的句子")
        t0 = time.time()
        await click('[data-quick="entry"]')
        await asyncio.sleep(0.8)
        await recap()
        if await c.js("!!(document.querySelector('[data-mode=\"para\"]') && !document.querySelector('[data-mode=\"para\"]').classList.contains('on'))"):
            await click('[data-mode="para"]')
        await until("document.querySelector('textarea') && document.querySelector('#txList .dt, #txList table, #txList .card')", 40)
        await recap()
        c.ff.append((t0, time.time(), 1.0))
        await click("textarea", pause=0.3)
        text = "早上買蛋餅 45，接著去學校買了10元自動鉛筆，晚上全聯買牙膏 89"
        await c.js("""(async (t) => { const ta = document.querySelector('textarea'); ta.focus(); ta.value = '';
                      for (const ch of t) { ta.value += ch; ta.dispatchEvent(new Event('input', {bubbles:true}));
                      await new Promise(r => setTimeout(r, 80)); } })(%s)""" % json.dumps(text), wait=True)
        await asyncio.sleep(1)
        await click("#paraGo")
        await cap("AI 解析中", "本機沒有接模型（線上接 Claude）：後端回 503，前端先用規則拆好，一樣要人確認才存")
        t0 = time.time()
        await until("document.getElementById('paraSave')", 40)
        c.ff.append((t0, time.time(), 2.5))
        await asyncio.sleep(1)
        await c.js("var r=document.querySelector('.btbl, #paraSave'); if(r) r.scrollIntoView({block:'center'})")
        await cap("解析結果", "備註只留項目（「接著去學校買了10元自動鉛筆」→「自動鉛筆」），原句小字附在下面對照")
        await asyncio.sleep(8)
        await click("#paraSave")
        t0 = time.time()
        await until("!document.getElementById('paraSave')", 20)
        await asyncio.sleep(1.5)
        c.ff.append((t0, time.time(), 1.5))
        await c.js("window.scrollTo({top: 0, behavior: 'smooth'})")
        await cap("確認寫入", "3 筆寫進資料庫，出現在收支明細；備註是項目")
        await asyncio.sleep(6)

        step[0] += 1
        shown.update(title="統計", desc="收支對照、錢花在哪：數字與總覽、明細同一個來源")
        await go(LOCAL + "/#/stats", ready="document.querySelector('.donut, svg circle, .dt')")
        step[0] -= 1
        await cap("統計", "收支對照、錢花在哪：數字與總覽、明細同一個來源")
        await asyncio.sleep(5)

        step[0] += 1
        shown.update(title="財務建議", desc="按「產生這個月的建議」：數字由資料庫先算好")
        await go(LOCAL + "/#/advice", ready="document.getElementById('advGen')")
        step[0] -= 1
        await cap("財務建議", "按「產生這個月的建議」：數字由資料庫先算好，模型只寫句子；本機沒接模型就用同一批數字整理")
        await asyncio.sleep(2)
        await click("#advGen")
        t0 = time.time()
        await asyncio.sleep(2)
        await until("document.getElementById('advGen') && !document.getElementById('advGen').disabled", 45)
        c.ff.append((t0, time.time(), 3.0))
        await asyncio.sleep(1)
        await click(".ad__h")
        await asyncio.sleep(1)
        await cap("建議的依據", "每個數字都附算式、找得到出處；線上 Claude 寫的也逐一檢查，不合格的那一則不顯示")
        await asyncio.sleep(7)

        await c.js("window.scrollTo({top: 0, behavior: 'smooth'})")
        await asyncio.sleep(0.8)
        await click("#bell")
        await until("document.querySelector('.bell__del')", 10)
        await asyncio.sleep(0.8)
        await cap("刪除", "登記的資料都能刪：通知每則右邊的 ×、已讀的一次清掉；建議 6 秒內可復原；自訂分類、帳號本身也能刪")
        await asyncio.sleep(3)
        await click(".bell__del")
        await asyncio.sleep(3)
        await click("#bell")
        await asyncio.sleep(1)

        step[0] += 1
        shown.update(title="預算", desc="總覽的「調整預算 ›」直接打開個人資料的每月預算")
        await go(LOCAL + "/#/", ready="document.querySelector('a[href=\"#/profile/budget\"]')")
        await asyncio.sleep(1)
        await click('a[href="#/profile/budget"]')
        t0 = time.time()
        await until("document.querySelector('#fold-bud input[data-budget]') || document.querySelectorAll('#fold-bud input').length > 2", 40)
        await recap()
        c.ff.append((t0, time.time(), 1.0))
        await asyncio.sleep(1.5)
        step[0] -= 1
        await cap("預算", "總覽的「調整預算 ›」直接打開個人資料的每月預算")
        await asyncio.sleep(5)

        step[0] += 1
        shown.update(title="帳本", desc="整頁只有一顆「開一本帳」，常設或活動在表單裡選")
        await go(LOCAL + "/#/groups", ready="document.querySelector('[data-fold=\"gnew\"]') && document.querySelector('.lgl')")
        step[0] -= 1
        await cap("帳本", "不分常設、活動，只有一份清單；一本帳平常只佔一行，點開才有細節")
        await asyncio.sleep(3.5)
        await click('[data-fold="gnew"]')
        await asyncio.sleep(0.8)
        await click("#gnName", pause=0.3)
        await c.js("""(async (t) => { const el = document.getElementById('gnName'); el.focus(); el.value = '';
                      for (const ch of t) { el.value += ch; await new Promise(r => setTimeout(r, 90)); } })(%s)"""
                   % json.dumps("沖繩旅遊"), wait=True)
        await click("#gnEnd", pause=0.4, do=False)
        await cap("開一本帳", "填名字就好；結束日選填，旅行這種有結束日的再填（示範到這裡，不真的建立）")
        await asyncio.sleep(5)

        await go(LOCAL + "/#/", ready="document.querySelector('[data-nav=\"theme\"]')")
        await click('[data-nav="theme"]')
        await until("document.querySelectorAll('.thm__i').length > 3", 20)
        await recap()
        await point()
        await cap("主題", "自己一頁，八套排成卡片，按一下就換；存在帳號上，換裝置登入也一樣")
        await asyncio.sleep(2)
        await click('[data-theme-pick="tech"]')
        await asyncio.sleep(3)
        await click('[data-theme-pick="sky"]')
        await asyncio.sleep(2)

        step[0] += 1
        shown.update(title="家庭成員", desc="邀請碼過期會被拒絕、重複加入會被擋；家長照看子女")
        await go(LOCAL + "/#/members", ready="document.querySelector('.mcard, .mem, [data-open]') || document.body.innerText.includes('邀請家人')")
        step[0] -= 1
        await cap("家庭成員", "邀請碼過期會被拒絕、重複加入會被擋；家長照看子女")
        await asyncio.sleep(5)
        step[0] += 1
        shown.update(title="子女的紀錄", desc="家長看得到照看的孩子記了什麼，也在這裡設定每月零用金")
        await go(LOCAL + "/#/member/%s" % uid_of("kid"), ready="document.querySelector('[data-allow]')")
        step[0] -= 1
        await cap("子女的紀錄", "家長看得到照看的孩子記了什麼，也在這裡設定每月零用金")
        await asyncio.sleep(5)

        # ---------- 子女 ----------
        step[0] += 1
        shown.update(title="子女總覽", desc="換成子女的帳號")
        await login("kid")
        await go(LOCAL + "/?r=%d#/" % (time.time() * 1000), ready="document.querySelector('.wal__v')")
        await asyncio.sleep(1)
        step[0] -= 1
        await cap("子女總覽", "家長給的零用金算在可花上限裡；子女只看得到自己的帳")
        await asyncio.sleep(6)
        step[0] += 1
        shown.update(title="權限隔離", desc="子女打開家長的紀錄 → 被拒絕")
        await go(LOCAL + "/#/member/%s" % uid_of("dad"), ready="document.body.innerText.includes('看不到')")
        step[0] -= 1
        await cap("權限隔離", "子女打開家長的紀錄 → 被拒絕；家長的帳只有家長自己與照看他的人看得到")
        await asyncio.sleep(5)

        # ---------- 平台管理 ----------
        step[0] += 1
        shown.update(title="平台管理", desc="換成平台管理員")
        await login("admin")
        await go(LOCAL + "/?r=%d#/admin" % (time.time() * 1000), ready="document.querySelector('#admUsers .lamp')")
        await asyncio.sleep(1)
        step[0] -= 1
        await cap("平台管理", "每個帳號一個紅綠燈（每 10 秒更新）、被規則擋下的安全事件、即時的錯誤訊息；讀不到任何人的帳")
        await asyncio.sleep(7)
        await c.js("var e=document.getElementById('admErrors'); if(e) e.scrollIntoView({block:'center'})")
        await asyncio.sleep(4)

        # ---------- 手機版 ----------
        await c.send("Emulation.setDeviceMetricsOverride", width=375, height=812, deviceScaleFactor=1, mobile=True)
        await c.send("Page.stopScreencast")
        await c.send("Page.startScreencast", format="jpeg", quality=82, maxWidth=375, maxHeight=812, everyNthFrame=1)
        step[0] += 1
        shown.update(title="手機版", desc="底部分頁列；常用功能不再重複放明細、統計、建議")
        await login("dad")
        await go(LOCAL + "/?r=%d#/" % (time.time() * 1000), ready="document.querySelector('.wal__v') && document.querySelector('.bcard')")
        await asyncio.sleep(1)
        step[0] -= 1
        await cap("手機版", "底部分頁列；常用功能不再重複放明細、統計、建議")
        await asyncio.sleep(3)
        await c.js("window.scrollTo({top: 700, behavior: 'smooth'})")
        await asyncio.sleep(4)
        await c.js("localStorage.removeItem('fambudget.auth')")

        # ---------- 片尾 ----------
        await c.send("Page.stopScreencast")
        await c.send("Emulation.setDeviceMetricsOverride", width=W, height=H, deviceScaleFactor=1, mobile=False)
        await c.send("Page.startScreencast", format="jpeg", quality=82, maxWidth=W, maxHeight=H, everyNthFrame=1)
        await c.js("localStorage.removeItem('fambudget.auth')")
        shown.clear()
        await go(card_url("end", card_html("RESULT", "測試結果", [
            "兩輪 26 個問題全部修正並在線上驗證；第三輪照使用者的回饋把畫面收乾淨",
            "詳細內容：家庭記帳_測試報告.pdf、家庭記帳_使用者評分與改善建議.pdf"],
            [("99→100%", "AI 解析整題完全正確"), ("11 / 11", "AI 建議數字全對"), ("4 / 4", "過期後關閉存取"),
             ("57.6→85.7", "使用者評分平均")])), 1, keep=0.5)
        await asyncio.sleep(6)
        c.recording = False
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tokens", required=True)
    args = ap.parse_args()
    with io.open(args.tokens, encoding="utf-8") as f:
        tokens = json.load(f)
    # 免費主機閒置會睡：先把線上後端叫醒，不然第一個請求（過期的驗證連結那一步）會等到前端說連不上
    for _ in range(6):
        try:
            if httpx.get(BACKEND + "/openapi.json", timeout=90).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(5)
    exe = next(p for p in CHROME if os.path.exists(p))
    workdir = tempfile.mkdtemp(prefix="fambudget-video-")
    profile = os.path.join(workdir, "profile")
    port = 9335
    proc = subprocess.Popen([exe, "--headless=new", "--remote-debugging-port=%d" % port, "--user-data-dir=" + profile,
                             "--hide-scrollbars", "--no-first-run", "--lang=zh-TW", "--window-size=%d,%d" % (W, H),
                             "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            try:
                tabs = httpx.get("http://127.0.0.1:%d/json/list" % port, timeout=1).json()
                page = next(t for t in tabs if t.get("type") == "page")
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.25)
        frames, ff = asyncio.run(run(page["webSocketDebuggerUrl"], tokens, workdir))
        print("frames:", len(frames), "seconds:", round(frames[-1][0] - frames[0][0], 1) if frames else 0)
        out = os.path.join(HERE, "家庭記帳_測試流程.mp4")
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
