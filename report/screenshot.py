"""
報告用的畫面截圖：用本機的 Chrome（無頭模式）登入，逐頁截高解析度的圖到 report/assets/。

    # 先開本機後端與前端，用 report/qa/record_demo.py --target local 走過一次完整流程（從空帳號開始，帳上才有資料），然後：
    python report/screenshot.py --accounts <帳密 JSON> --front http://localhost:5195 --api http://127.0.0.1:8010

帳密 JSON：{"parent": {"email", "password"}, "kid": {...}, "admin": {...}}——只給本機用。
不在登入畫面打密碼：用 API 登入拿權杖，放進瀏覽器的 localStorage（跟前端登入後存的一樣）。
段落記帳那張（parse.png）要真的模型才有意義，本機沒接模型，預設不重截（--only parse 才截）。
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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "report", "assets")
TOUR_KEY = 'fambudget.tour'          # frontend/js/app.js 的 TOUR_KEY（後面接 .<使用者 id>）
CHROME = [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
          r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"]

#: (檔名, 誰登入, 網址的 hash, 寬, 高, 截圖前要在頁面上做的事（JS）, 等幾秒)
#: 誰登入後面接 "@活動名稱" 是先切到那個活動（活動模式的總覽）
SHOTS = [
    ("home", "parent", "#/", 1280, 800, "", 5),          # 第一張：瀏覽器剛開，等久一點
    ("home_panel", "parent", "#/", 1280, 800, "PANEL", 3),
    ("entry", "parent", "#/entry", 1280, 800, "", 3),
    ("groups", "parent", "#/groups", 1280, 800, "", 3),
    ("activity_home", "parent@沖繩畢業旅行", "#/", 1280, 800, "", 3),
    ("stats", "parent", "#/stats", 1280, 800, "", 3),
    ("advice", "parent", "#/advice", 1280, 800, "", 3),
    ("members", "parent", "#/members", 1280, 800, "", 3),
    ("profile", "parent", "#/profile", 1280, 800, "", 3),
    ("kid_home", "kid", "#/", 1280, 800, "", 3),
    ("home_mobile", "parent", "#/", 390, 844, "", 3),
    ("admin", "admin", "#/admin", 1280, 800, "", 3),
    ("admin_mobile", "admin", "#/admin", 390, 844, "", 3),
    ("parse", "parent", "#/entry", 1280, 800, "PARSE", 8),
]
DEFAULT_SKIP = {"parse"}

#: 總覽下方的面板捲到畫面中間
PANEL_JS = "document.querySelector('.hpanel') && document.querySelector('.hpanel').scrollIntoView({block: 'center'})"

#: 段落記帳：按「記一筆」、選段落記帳、貼一段話、按解析
PARSE_JS = r"""
(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const byText = (sel, txt) => [...document.querySelectorAll(sel)].find(e => e.textContent.trim().includes(txt));
  const tile = byText('a,button,[data-quick],.qt', '記一筆'); if (tile) tile.click();
  await sleep(1500);
  const ta = document.querySelector('textarea');
  if (!ta) return 'no textarea';
  ta.focus();
  ta.value = '早上買早餐55，中午跟同事吃飯320，晚上加油，昨天全聯買衛生紙199';
  ta.dispatchEvent(new Event('input', {bubbles: true}));
  await sleep(300);
  const go = byText('button', '解析');
  if (go) go.click();
  return go ? 'clicked' : 'no button';
})()
"""


def login(api, acc):
    """用 API 登入拿權杖（本機的帳號），回傳 (權杖, 使用者 id, 活動名稱 → id)"""
    r = httpx.post(api + "/api/auth/login", json={"email": acc["email"], "password": acc["password"]}, timeout=60)
    r.raise_for_status()
    d = r.json()
    tok = {k: d[k] for k in ("accessToken", "refreshToken", "expiresIn")}
    tok["savedAt"] = int(time.time() * 1000)
    uid = json.loads(base64.urlsafe_b64decode(d["accessToken"].split(".")[1] + "==="))["sub"]
    gs = httpx.get(api + "/api/groups", headers={"authorization": "Bearer " + d["accessToken"]}, timeout=60).json()
    return tok, str(uid), {g["name"]: g["id"] for g in gs.get("groups", [])}


async def cdp(ws_url, shots, people, front, api):
    async with websockets.connect(ws_url, max_size=64 * 1024 * 1024) as ws:
        seq = 0

        async def send(method, **params):
            nonlocal seq
            seq += 1
            me = seq
            await ws.send(json.dumps({"id": me, "method": method, "params": params}))
            while True:
                msg = json.loads(await ws.recv())
                if msg.get("id") == me:
                    if "error" in msg:
                        raise RuntimeError("%s: %s" % (method, msg["error"]))
                    return msg.get("result", {})

        async def js(expr, wait=False):
            r = await send("Runtime.evaluate", expression=expr, awaitPromise=wait, returnByValue=True)
            return r.get("result", {}).get("value")

        await send("Page.enable")
        await send("Runtime.enable")
        await send("Page.navigate", url=front + "/docs/guide.html")
        await asyncio.sleep(1.5)
        await js("localStorage.setItem('fambudget.api', %s)" % json.dumps(api))
        for name, who, hash_, w, h, action, wait in shots:
            who, _, activity = who.partition("@")
            tok, uid, groups = people[who]
            await send("Emulation.setDeviceMetricsOverride", width=w, height=h, deviceScaleFactor=2, mobile=w < 600)
            # 權杖、導覽看過（記在帳號上：fambudget.tour.<id>）、要看哪一個活動（沒有就是個人）
            await js("localStorage.setItem('fambudget.auth', %s); localStorage.setItem(%s, 'done'); localStorage.setItem('fambudget.group', %s)"
                     % (json.dumps(json.dumps(tok)), json.dumps(TOUR_KEY + "." + uid), json.dumps(groups.get(activity, "") if activity else "")))
            await send("Page.navigate", url=front + "/?r=%d%s" % (time.time() * 1000, hash_))
            await asyncio.sleep(wait + 1.5)          # 資料到了、淡入動畫也跑完
            if action == "PARSE":
                r = await js(PARSE_JS, wait=True)
                print("  段落記帳：", r)
                await asyncio.sleep(wait)
            elif action == "PANEL":
                await js(PANEL_JS)
                await asyncio.sleep(1)
            shot = await send("Page.captureScreenshot", format="png")
            path = os.path.join(OUT, name + ".png")
            with open(path, "wb") as f:
                f.write(base64.b64decode(shot["data"]))
            print("  " + path)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--accounts", required=True, help="本機帳號的帳密 JSON：{parent, kid, admin}")
    ap.add_argument("--front", default="http://localhost:5195")
    ap.add_argument("--api", default="http://127.0.0.1:8010")
    ap.add_argument("--only", default="", help="只截這幾張（逗號分隔）")
    args = ap.parse_args()
    with io.open(args.accounts, encoding="utf-8") as f:
        accounts = json.load(f)
    api = args.api.rstrip("/")
    people = {who: login(api, acc) for who, acc in accounts.items() if acc}
    only = args.only.split(",") if args.only else None
    shots = [s for s in SHOTS if (s[0] in only if only else s[0] not in DEFAULT_SKIP) and s[1].split("@")[0] in people]
    os.makedirs(OUT, exist_ok=True)

    exe = next(p for p in CHROME if os.path.exists(p))
    profile = tempfile.mkdtemp(prefix="fambudget-shot-")
    port = 9333
    proc = subprocess.Popen([exe, "--headless=new", "--remote-debugging-port=%d" % port,
                             "--user-data-dir=" + profile, "--hide-scrollbars", "--no-first-run",
                             "--lang=zh-TW", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                tabs = httpx.get("http://127.0.0.1:%d/json/list" % port, timeout=1).json()
                page = next(t for t in tabs if t.get("type") == "page")
                break
            except Exception:  # noqa: BLE001  Chrome 還沒起來
                time.sleep(0.2)
        asyncio.run(cdp(page["webSocketDebuggerUrl"], shots, people, args.front.rstrip("/"), api))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        shutil.rmtree(profile, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
