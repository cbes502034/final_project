"""完整測試流程的示範影片：本機 Chrome（無頭）依序操作線上站，逐格擷取畫面，疊上中文字幕，合成 MP4。

    python report/qa/record_demo.py --tokens <只含 access token 的 JSON>   → report/qa/家庭記帳_測試流程.mp4

⚠️ 只帶 30 分鐘就過期的 access token，不帶 refresh token；畫面上不輸入任何密碼。
⚠️ 會真的寫入：家長帳號用段落記帳記 3 筆、產生一次財務建議（測試帳號）。
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import io
import json
import os
import shutil
import subprocess
import tempfile
import time

import httpx
import websockets
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
FRONT = "https://fambudget-web.onrender.com"
CHROME = [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
          r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"]
W, H = 1280, 800

#: 驗證信實測時的第一封（11:09 寄出、11:12 過期）：拿來示範「過期的連結會被拒絕」
EXPIRED_VERIFY = ("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZW1haWwiOiJjYmVzNTAyMDM0QGdtYWlsLmNvbSIsInR5cGUiOiJ2ZXJp"
                  "ZnlfZW1haWwiLCJpYXQiOjE3OTIzNzkzNjksImV4cCI6MTc5MjM3OTU0OX0.DPhhMJB2BCiYaxjOpP5DOzIAZeAHN7tOXMZu50bA2V8")

CAPTION_JS = r"""
(function (step, total, title, desc) {
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
    tag.textContent = 'LIVE · fambudget-web.onrender.com';
    document.documentElement.appendChild(tag);
  }
  var small = innerWidth < 600;
  el.style.padding = small ? '10px 14px 12px' : '14px 28px 16px';
  el.innerHTML = '<span style="font:700 ' + (small ? 12 : 15) + 'px Consolas,monospace;color:#0ABAB5;white-space:nowrap">' + step + ' / ' + total + '</span>' +
    '<span style="font-size:' + (small ? 17 : 21) + 'px;font-weight:700;white-space:nowrap">' + title + '</span>' +
    '<span style="font-size:' + (small ? 13 : 15) + 'px;color:#a9b6c3">' + desc + '</span>';
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
        total = 18
        step = [0]

        shown = {}

        async def cap(title, desc):
            step[0] += 1
            shown.update(title=title, desc=desc)
            await recap()

        async def recap():
            # 換頁（重新載入）會把字幕清掉：每次換頁後立刻補上目前這一步的字幕
            if shown:
                await c.js("(%s)(%d, %d, %s, %s)" % (CAPTION_JS, step[0], total, json.dumps(shown["title"]),
                                                     json.dumps(shown["desc"])))

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
            c.ff.append((t0, time.time(), keep))

        async def login(who):
            await c.js("localStorage.setItem('fambudget.auth', %s); localStorage.setItem('fambudget.tour','done')"
                       % json.dumps(json.dumps(tokens[who])))

        async def until(expr, timeout=40):
            t0 = time.time()
            while time.time() - t0 < timeout:
                if await c.js(expr):
                    return True
                await asyncio.sleep(0.5)
            return False

        def card_url(name, html):
            path = os.path.join(workdir, name + ".html")
            with io.open(path, "w", encoding="utf-8") as f:
                f.write(html)
            return "file:///" + path.replace("\\", "/")

        # 片頭（不算步驟）
        await go(card_url("open", card_html("FAMBUDGET · QA WALKTHROUGH · 2026-10-19", "家庭記帳<br>完整測試流程",
                                            ["在 Render 部署後的正式網站上實測：未登入 → 家長記帳與 AI → 子女與權限 → 手機版",
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
        await c.js("var b=[...document.querySelectorAll('a,button')].find(e=>e.textContent.includes('開始使用')); if(b) b.click()")
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

        # ---------- 家長 ----------
        step[0] += 1
        shown.update(title="家長總覽", desc="換成家長的帳號")
        await go(FRONT + "/docs/guide.html", 1.5, keep=0.1)
        await login("dad")
        await go(FRONT + "/?r=%d#/" % (time.time() * 1000), ready="document.querySelector('.wal__v') && document.querySelector('.bcard')")
        await asyncio.sleep(1)
        step[0] -= 1
        await cap("家長總覽", "收入 52,000、支出 22,510 → 可花上限 32,000，這個月還可以花 9,490；餐飲預算已用 145%")
        await asyncio.sleep(6)

        await cap("段落記帳", "一句話記好幾筆：直接打一段平常講話的句子")
        t0 = time.time()
        await c.js("var b=document.querySelector('[data-quick=\"entry\"]'); if(b) b.click()")
        await asyncio.sleep(0.8)
        await recap()
        await c.js("var m=document.querySelector('[data-mode=\"para\"]'); if(m && !m.classList.contains('on')) m.click()")
        await until("document.querySelector('textarea') && document.querySelector('#txList .dt, #txList table, #txList .card')", 40)
        await recap()
        c.ff.append((t0, time.time(), 1.0))
        text = "早餐蛋餅 45，捷運 30，晚上全聯買牙膏 89"
        await c.js("""(async (t) => { const ta = document.querySelector('textarea'); ta.focus(); ta.value = '';
                      for (const ch of t) { ta.value += ch; ta.dispatchEvent(new Event('input', {bubbles:true}));
                      await new Promise(r => setTimeout(r, 90)); } })(%s)""" % json.dumps(text), wait=True)
        await asyncio.sleep(1)
        await c.js("document.getElementById('paraGo').click()")
        await cap("AI 解析中", "線上的 Claude 把這段話切成一筆一筆；後端再逐欄跟原句對事實")
        t0 = time.time()
        await until("document.getElementById('paraSave')", 40)
        c.ff.append((t0, time.time(), 2.5))
        await asyncio.sleep(1)
        await c.js("var r=document.querySelector('.prs, #paraSave'); if(r) r.scrollIntoView({block:'center'})")
        await cap("解析結果", "切成 3 筆：日期、金額、收支、分類、店家都對照原句；缺的欄位會標紅、補齊才能存")
        await asyncio.sleep(7)
        await c.js("document.getElementById('paraSave').click()")
        t0 = time.time()
        await until("!document.getElementById('paraSave')", 20)
        await asyncio.sleep(1.5)
        c.ff.append((t0, time.time(), 1.5))
        await c.js("window.scrollTo({top: 0, behavior: 'smooth'})")
        await cap("確認寫入", "3 筆寫進資料庫，出現在收支明細；每筆都附原句，來源標記為段落（AI）")
        await asyncio.sleep(6)

        step[0] += 1
        shown.update(title="統計", desc="收支對照、錢花在哪：數字與總覽、明細同一個來源")
        await go(FRONT + "/#/stats", ready="document.querySelector('.donut, svg circle, .dt')")
        step[0] -= 1
        await cap("統計", "收支對照、錢花在哪：數字與總覽、明細同一個來源")
        await asyncio.sleep(5)

        step[0] += 1
        shown.update(title="財務建議", desc="按「產生這個月的建議」：數字由資料庫先算好，AI 只負責寫成句子")
        await go(FRONT + "/#/advice", ready="document.getElementById('advGen')")
        step[0] -= 1
        await cap("財務建議", "按「產生這個月的建議」：數字由資料庫先算好，AI 只負責寫成句子")
        await asyncio.sleep(2)
        await c.js("var b=document.getElementById('advGen'); if(b) b.click()")
        t0 = time.time()
        await asyncio.sleep(2)
        await until("document.getElementById('advGen') && !document.getElementById('advGen').disabled", 45)
        c.ff.append((t0, time.time(), 3.0))
        await asyncio.sleep(1)
        await c.js("var h=document.querySelector('.ad__h'); if(h) h.click()")
        await asyncio.sleep(1)
        await cap("建議的依據", "每個數字都要找得到出處、不能套錯分類，不合格的那一則不顯示")
        await asyncio.sleep(7)

        step[0] += 1
        shown.update(title="預算", desc="總覽的「調整預算 ›」直接打開個人資料的每月預算（這一輪修好的）")
        await go(FRONT + "/#/", ready="document.querySelector('a[href=\"#/profile/budget\"]')")
        await c.js("document.querySelector('a[href=\"#/profile/budget\"]').scrollIntoView({block:'center'})")
        await asyncio.sleep(2)
        t0 = time.time()
        await c.js("document.querySelector('a[href=\"#/profile/budget\"]').click()")
        await until("document.querySelector('#fold-bud input[data-budget]') || document.querySelectorAll('#fold-bud input').length > 2", 40)
        await recap()
        c.ff.append((t0, time.time(), 1.0))
        await asyncio.sleep(1.5)
        step[0] -= 1
        await cap("預算", "總覽的「調整預算 ›」直接打開個人資料的每月預算（這一輪修好的）")
        await asyncio.sleep(5)

        step[0] += 1
        shown.update(title="家庭成員", desc="邀請碼過期會被拒絕、重複加入會被擋；家長照看子女")
        await go(FRONT + "/#/members", ready="document.querySelector('.mcard, .mem, [data-open]') || document.body.innerText.includes('邀請家人')")
        step[0] -= 1
        await cap("家庭成員", "邀請碼過期會被拒絕、重複加入會被擋；家長照看子女")
        await asyncio.sleep(5)
        step[0] += 1
        shown.update(title="子女的紀錄", desc="家長看得到照看的孩子記了什麼，也在這裡設定每月零用金 3,000")
        await go(FRONT + "/#/member/3", ready="document.querySelector('[data-allow]')")
        step[0] -= 1
        await cap("子女的紀錄", "家長看得到照看的孩子記了什麼，也在這裡設定每月零用金 3,000")
        await asyncio.sleep(5)

        # ---------- 子女 ----------
        step[0] += 1
        shown.update(title="子女總覽", desc="換成子女的帳號")
        await go(FRONT + "/docs/guide.html", 1.5, keep=0.1)
        await login("kid")
        await go(FRONT + "/?r=%d#/" % (time.time() * 1000), ready="document.querySelector('.wal__v') && document.getElementById('mailAgain')")
        await asyncio.sleep(1)
        step[0] -= 1
        await cap("子女總覽", "沒記零用金收入，可花上限仍是 3,000（含零用金）；還沒確認 email，上方會提醒並可以重寄")
        await asyncio.sleep(7)
        step[0] += 1
        shown.update(title="權限隔離", desc="子女打開家長的紀錄 → 被拒絕")
        await go(FRONT + "/#/member/1", ready="document.body.innerText.includes('看不到')")
        step[0] -= 1
        await cap("權限隔離", "子女打開家長的紀錄 → 被拒絕；家長的帳只有家長自己與照看他的人看得到")
        await asyncio.sleep(5)

        # ---------- 手機版 ----------
        await c.send("Emulation.setDeviceMetricsOverride", width=375, height=812, deviceScaleFactor=1, mobile=True)
        await c.send("Page.stopScreencast")
        await c.send("Page.startScreencast", format="jpeg", quality=82, maxWidth=375, maxHeight=812, everyNthFrame=1)
        step[0] += 1
        shown.update(title="手機版", desc="底部分頁列；常用功能不再重複放明細、統計、建議")
        await go(FRONT + "/?r=%d#/" % (time.time() * 1000), ready="document.querySelector('.wal__v') && document.querySelector('.bcard')")
        await asyncio.sleep(1)
        step[0] -= 1
        await cap("手機版", "底部分頁列；常用功能不再重複放明細、統計、建議")
        await asyncio.sleep(3)
        await c.js("window.scrollTo({top: 700, behavior: 'smooth'})")
        await asyncio.sleep(4)

        # ---------- 片尾 ----------
        await c.send("Page.stopScreencast")
        await c.send("Emulation.setDeviceMetricsOverride", width=W, height=H, deviceScaleFactor=1, mobile=False)
        await c.send("Page.startScreencast", format="jpeg", quality=82, maxWidth=W, maxHeight=H, everyNthFrame=1)
        await c.js("localStorage.removeItem('fambudget.auth')")
        shown.clear()
        await go(card_url("end", card_html("RESULT", "測試結果", [
            "17 個問題全部修正、重新部署，並在線上驗證", "詳細內容：家庭記帳_測試報告.pdf、家庭記帳_使用者評分與改善建議.pdf"],
            [("99→100%", "AI 解析整題完全正確"), ("11 / 11", "AI 建議數字全對"), ("4 / 4", "過期後關閉存取"),
             ("57.6→83.6", "使用者評分平均")])), 1, keep=0.5)
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
