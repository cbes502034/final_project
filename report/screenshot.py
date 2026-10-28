"""
專案報告「個人帳本」那一頁的截圖：用本機的 Chrome（無頭模式）登入，截高解析度的圖到 report/assets/entry.png。
（其他頁的畫面是 report/qa/record_demo.py --trial --snaps 在同一輪拍的，在 report/assets/demo/。）

    # 先開本機後端與前端，用 report/qa/record_demo.py --target local 走過一次完整流程（從空帳號開始，帳上才有資料），然後：
    python report/screenshot.py --accounts <帳密 JSON> --front http://localhost:5195 --api http://127.0.0.1:8010

帳密 JSON：{"parent": {"email", "password"}, ...}——只給本機用，只用到 parent。
不在登入畫面打密碼：用 API 登入拿權杖，放進瀏覽器的 localStorage（跟前端登入後存的一樣）。
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

#: (檔名, 網址的 hash, 寬, 高, 等幾秒)
SHOT = ("entry", "#/entry", 1280, 800, 5)          # 瀏覽器剛開，等久一點


def login(api, acc):
    """用 API 登入拿權杖（本機的帳號），回傳 (權杖, 使用者 id)"""
    r = httpx.post(api + "/api/auth/login", json={"email": acc["email"], "password": acc["password"]}, timeout=60)
    r.raise_for_status()
    d = r.json()
    tok = {k: d[k] for k in ("accessToken", "refreshToken", "expiresIn")}
    tok["savedAt"] = int(time.time() * 1000)
    uid = json.loads(base64.urlsafe_b64decode(d["accessToken"].split(".")[1] + "==="))["sub"]
    return tok, str(uid)


async def cdp(ws_url, tok, uid, front, api):
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

        async def js(expr):
            await send("Runtime.evaluate", expression=expr, returnByValue=True)

        name, hash_, w, h, wait = SHOT
        await send("Page.enable")
        await send("Runtime.enable")
        await send("Page.navigate", url=front + "/docs/guide.html")
        await asyncio.sleep(1.5)
        await send("Emulation.setDeviceMetricsOverride", width=w, height=h, deviceScaleFactor=2, mobile=False)
        # API 位址、權杖、導覽看過（記在帳號上：fambudget.tour.<id>）、看個人（不是活動）
        await js("localStorage.setItem('fambudget.api', %s); localStorage.setItem('fambudget.auth', %s);"
                 "localStorage.setItem(%s, 'done'); localStorage.setItem('fambudget.group', '')"
                 % (json.dumps(api), json.dumps(json.dumps(tok)), json.dumps(TOUR_KEY + "." + uid)))
        await send("Page.navigate", url=front + "/?r=%d%s" % (time.time() * 1000, hash_))
        await asyncio.sleep(wait + 1.5)          # 資料到了、淡入動畫也跑完
        shot = await send("Page.captureScreenshot", format="png")
        path = os.path.join(OUT, name + ".png")
        with open(path, "wb") as f:
            f.write(base64.b64decode(shot["data"]))
        print("  " + path)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--accounts", required=True, help="本機帳號的帳密 JSON：{parent, ...}")
    ap.add_argument("--front", default="http://localhost:5195")
    ap.add_argument("--api", default="http://127.0.0.1:8010")
    args = ap.parse_args()
    with io.open(args.accounts, encoding="utf-8") as f:
        accounts = json.load(f)
    api = args.api.rstrip("/")
    tok, uid = login(api, accounts["parent"])
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
        asyncio.run(cdp(page["webSocketDebuggerUrl"], tok, uid, args.front.rstrip("/"), api))
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
