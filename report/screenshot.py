"""
報告用的畫面截圖：用本機的 Chrome（無頭模式）以示範帳號登入，逐頁截高解析度的圖到 report/assets/。

    # 先開本機後端與前端、跑 backend/tools/demo_seed.py 拿到權杖檔，然後：
    python report/screenshot.py --tokens <暫存資料夾>/demo_tokens.json --front http://localhost:5195 --api http://localhost:8010

不在登入畫面打密碼：直接把 demo_seed.py 拿到的權杖放進瀏覽器的 localStorage（跟前端登入後存的一樣）。
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
TOUR_KEY = 'fambudget.tour'          # frontend/js/app.js 的 TOUR_KEY
CHROME = [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
          r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"]

#: (檔名, 誰登入, 網址的 hash, 寬, 高, 截圖前要在頁面上做的事（JS）, 等幾秒)
SHOTS = [
    ("home", "dad", "#/", 1280, 800, "", 2.5),
    ("entry", "dad", "#/entry", 1280, 800, "", 2.5),
    ("groups", "dad", "#/groups", 1280, 800, "", 2.5),
    ("stats", "dad", "#/stats", 1280, 800, "", 3),
    ("advice", "dad", "#/advice", 1280, 800, "", 2.5),
    ("members", "dad", "#/members", 1280, 800, "", 2.5),
    ("profile", "dad", "#/profile", 1280, 800, "", 2.5),
    ("kid_home", "kid", "#/", 1280, 800, "", 2.5),
    ("home_mobile", "dad", "#/", 390, 844, "", 2.5),
    ("parse", "dad", "#/", 1280, 800, "PARSE", 8),
]

#: 段落記帳：按「記一筆」、選段落記帳、貼一段話、按解析
PARSE_JS = r"""
(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const byText = (sel, txt) => [...document.querySelectorAll(sel)].find(e => e.textContent.trim().includes(txt));
  const tile = byText('a,button,[data-quick],.qt', '記一筆'); if (tile) tile.click();
  await sleep(800);
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


async def cdp(ws_url, shots, tokens, front, api):
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

        await send("Page.enable")
        await send("Runtime.enable")
        await send("Page.navigate", url=front + "/?api=" + api)
        await asyncio.sleep(1.5)
        current = None
        for name, who, hash_, w, h, action, wait in shots:
            await send("Emulation.setDeviceMetricsOverride", width=w, height=h, deviceScaleFactor=2,
                       mobile=w < 600)
            if who != current:
                await send("Runtime.evaluate", expression="localStorage.setItem('fambudget.auth', %s)"
                           % json.dumps(json.dumps(tokens[who])))
                # 導覽提示（「第一次用？」）標成看過，截圖才不會被它蓋住
                await send("Runtime.evaluate", expression="localStorage.setItem(%s, 'done')" % json.dumps(TOUR_KEY))
                current = who
            await send("Page.navigate", url=front + "/" + hash_)
            await send("Runtime.evaluate", expression="location.reload()")
            await asyncio.sleep(wait if not action else 3)
            if action == "PARSE":
                r = await send("Runtime.evaluate", expression=PARSE_JS, awaitPromise=True, returnByValue=True)
                print("  段落記帳：", r.get("result", {}).get("value"))
                await asyncio.sleep(wait)
            shot = await send("Page.captureScreenshot", format="png")
            path = os.path.join(OUT, name + ".png")
            with open(path, "wb") as f:
                f.write(base64.b64decode(shot["data"]))
            print("  " + path)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tokens", required=True)
    ap.add_argument("--front", default="http://localhost:5195")
    ap.add_argument("--api", default="http://localhost:8010")
    ap.add_argument("--only", default="", help="只截這幾張（逗號分隔）")
    args = ap.parse_args()
    with io.open(args.tokens, encoding="utf-8") as f:
        tokens = json.load(f)
    shots = [s for s in SHOTS if not args.only or s[0] in args.only.split(",")]
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
        asyncio.run(cdp(page["webSocketDebuggerUrl"], shots, tokens, args.front.rstrip("/"), args.api.rstrip("/")))
    finally:
        proc.terminate()
        proc.wait(timeout=10)
        shutil.rmtree(profile, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
