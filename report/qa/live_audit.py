"""線上站的逐頁檢查：用本機 Chrome（無頭）以測試帳號打開每一頁，截圖並量出版面問題。

    python report/qa/live_audit.py --tokens <只含 access token 的 JSON>

每一頁記下：
  · 截圖（report/qa/shots/<名稱>.png）
  · 375／768／1280 三種寬度有沒有橫向溢出（scrollWidth − clientWidth）
  · 同一頁上「同一個名字」的按鈕／連結出現幾次、同一個 #/ 連結出現幾次——功能重複的線索
  · 這一頁的標題階層與主要文字（給使用者觀點評分用）
  · console 的錯誤

⚠️ 只帶 30 分鐘就過期的 access token，不帶 refresh token：截圖工具外流也拿不到長效憑證。
⚠️ 不按任何會寫入的按鈕（記一筆只打開、不送出；段落解析只解析、不確認）。
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

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "shots")
FRONT = "https://fambudget-web.onrender.com"
CHROME = [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
          r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"]

#: (名稱, 誰, hash, 截圖寬, 截圖高, 動作)
PAGES = [
    ("landing", None, "#/login", 1280, 860, "LANDING"),
    ("login", None, "#/login", 1280, 860, ""),
    ("register", None, "#/register", 1280, 860, ""),
    ("forgot", None, "#/forgot", 1280, 860, ""),
    ("home_parent", "dad", "#/", 1280, 900, ""),
    ("home_parent_family", "dad", "#/", 1280, 900, "FAMILY"),
    ("quick_entry", "dad", "#/", 1280, 900, "QUICK"),
    ("parse_batch", "dad", "#/", 1280, 900, "PARSE"),
    ("entry", "dad", "#/entry", 1280, 900, ""),
    ("stats", "dad", "#/stats", 1280, 900, ""),
    ("advice", "dad", "#/advice", 1280, 900, ""),
    ("members", "dad", "#/members", 1280, 900, ""),
    ("member_kid", "dad", "#/member/3", 1280, 900, ""),
    ("groups", "dad", "#/groups", 1280, 900, ""),
    ("profile", "dad", "#/profile", 1280, 900, ""),
    ("home_kid", "kid", "#/", 1280, 900, ""),
    ("entry_kid", "kid", "#/entry", 1280, 900, ""),
    ("advice_kid", "kid", "#/advice", 1280, 900, ""),
    ("members_kid", "kid", "#/members", 1280, 900, ""),
    ("home_parent_m", "dad", "#/", 375, 812, ""),
    ("entry_m", "dad", "#/entry", 375, 812, ""),
    ("stats_m", "dad", "#/stats", 375, 812, ""),
    ("members_m", "dad", "#/members", 375, 812, ""),
    ("home_kid_m", "kid", "#/", 375, 812, ""),
]

AUDIT_JS = r"""
(() => {
  const vis = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const clean = t => (t || '').replace(/\s+/g, ' ').trim();
  const ctl = [...document.querySelectorAll('a,button,[role=button],[data-nav]')].filter(vis);
  const labels = ctl.map(e => clean(e.getAttribute('aria-label') || e.textContent)).filter(Boolean);
  const count = a => a.reduce((m, x) => (m[x] = (m[x] || 0) + 1, m), {});
  const dupLabels = Object.entries(count(labels)).filter(([, c]) => c > 1);
  const hrefs = ctl.map(e => e.getAttribute('href') || (e.dataset && e.dataset.nav ? '#/' + e.dataset.nav : '')).filter(h => h && h.startsWith('#/'));
  const dupHrefs = Object.entries(count(hrefs)).filter(([, c]) => c > 1);
  const heads = [...document.querySelectorAll('h1,h2,h3,.sec__t,.head__t')].filter(vis).map(e => clean(e.textContent)).slice(0, 20);
  return JSON.stringify({ heads, dupLabels, dupHrefs, controls: labels.slice(0, 80),
    overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    text: clean(document.body.innerText).slice(0, 2500) });
})()
"""

OVERFLOW_JS = "document.documentElement.scrollWidth - document.documentElement.clientWidth"

ACTIONS = {
    "LANDING": "",            # #/login 第一次進來就是主頁
    "FAMILY": r"""(async () => { const b = [...document.querySelectorAll('button,a')].find(e => e.textContent.trim() === '全家');
                  if (b) b.click(); await new Promise(r => setTimeout(r, 2500)); return b ? 'family' : 'no toggle'; })()""",
    "QUICK": r"""(async () => { const b = [...document.querySelectorAll('button,a,[data-quick]')].find(e => e.textContent.trim().includes('記一筆'));
                 if (b) b.click(); await new Promise(r => setTimeout(r, 1200)); return b ? 'opened' : 'no button'; })()""",
    "PARSE": r"""(async () => {
        const sleep = ms => new Promise(r => setTimeout(r, ms));
        const byText = (sel, t) => [...document.querySelectorAll(sel)].find(e => e.textContent.trim().includes(t));
        const tile = byText('button,a,[data-quick]', '記一筆'); if (tile) tile.click();
        await sleep(900);
        const tab = byText('button,a', '段落'); if (tab) tab.click();
        await sleep(500);
        const ta = document.querySelector('textarea');
        if (!ta) return 'no textarea';
        ta.focus(); ta.value = '早上買早餐55，中午跟同事吃飯320，晚上加油，昨天全聯買衛生紙199';
        ta.dispatchEvent(new Event('input', { bubbles: true }));
        await sleep(300);
        const go = byText('button', '解析'); if (go) go.click();
        await sleep(9000);
        return go ? 'parsed' : 'no parse button';
    })()""",
}


async def run(ws_url, tokens, only):
    report = {}
    async with websockets.connect(ws_url, max_size=128 * 1024 * 1024) as ws:
        seq = 0
        errors = []

        async def send(method, **params):
            nonlocal seq
            seq += 1
            me = seq
            await ws.send(json.dumps({"id": me, "method": method, "params": params}))
            while True:
                msg = json.loads(await ws.recv())
                if msg.get("method") in ("Runtime.exceptionThrown",):
                    errors.append(msg["params"]["exceptionDetails"].get("text", ""))
                if msg.get("method") == "Runtime.consoleAPICalled" and msg["params"].get("type") == "error":
                    errors.append(" ".join(str(a.get("value", a.get("description", ""))) for a in msg["params"]["args"]))
                if msg.get("id") == me:
                    if "error" in msg:
                        raise RuntimeError("%s: %s" % (method, msg["error"]))
                    return msg.get("result", {})

        async def evaluate(js, wait=False):
            r = await send("Runtime.evaluate", expression=js, awaitPromise=wait, returnByValue=True)
            return r.get("result", {}).get("value")

        await send("Page.enable")
        await send("Runtime.enable")
        await send("Page.navigate", url=FRONT + "/docs/index.html")
        await asyncio.sleep(2)
        for name, who, hash_, w, h, action in PAGES:
            if only and name not in only:
                continue
            errors.clear()
            await send("Emulation.setDeviceMetricsOverride", width=w, height=h, deviceScaleFactor=1, mobile=w < 600)
            if who:
                await evaluate("localStorage.setItem('fambudget.auth', %s)" % json.dumps(json.dumps(tokens[who])))
            else:
                await evaluate("localStorage.removeItem('fambudget.auth')")
            await evaluate("localStorage.setItem('fambudget.tour', 'done')")
            # 網址帶一個不同的查詢參數：一定會重新載入，不會停在上一頁的狀態
            await send("Page.navigate", url="%s/?r=%d%s" % (FRONT, time.time() * 1000, hash_))
            await asyncio.sleep(6)
            note = ""
            if action and ACTIONS.get(action):
                note = await evaluate(ACTIONS[action], wait=True)
                await asyncio.sleep(1)
            audit = json.loads(await evaluate(AUDIT_JS) or "{}")
            # 三種寬度的橫向溢出（同一頁、同一個狀態）
            widths = {}
            for ww in (375, 768, 1280):
                await send("Emulation.setDeviceMetricsOverride", width=ww, height=h, deviceScaleFactor=1, mobile=ww < 600)
                await asyncio.sleep(0.6)
                widths[ww] = await evaluate(OVERFLOW_JS)
            await send("Emulation.setDeviceMetricsOverride", width=w, height=h, deviceScaleFactor=1, mobile=w < 600)
            await asyncio.sleep(0.6)
            shot = await send("Page.captureScreenshot", format="png", captureBeyondViewport=True)
            with open(os.path.join(OUT, name + ".png"), "wb") as f:
                f.write(base64.b64decode(shot["data"]))
            audit.update({"who": who, "hash": hash_, "width": w, "action": note, "overflowByWidth": widths,
                          "consoleErrors": list(errors)})
            report[name] = audit
            print("  %-20s overflow=%s dupLabels=%d errors=%d %s" % (
                name, widths, len(audit.get("dupLabels", [])), len(errors), note or ""), flush=True)
        await evaluate("localStorage.removeItem('fambudget.auth')")
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tokens", required=True)
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    with io.open(args.tokens, encoding="utf-8") as f:
        tokens = json.load(f)
    os.makedirs(OUT, exist_ok=True)
    exe = next(p for p in CHROME if os.path.exists(p))
    profile = tempfile.mkdtemp(prefix="fambudget-audit-")
    port = 9334
    proc = subprocess.Popen([exe, "--headless=new", "--remote-debugging-port=%d" % port, "--user-data-dir=" + profile,
                             "--hide-scrollbars", "--no-first-run", "--lang=zh-TW", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            try:
                tabs = httpx.get("http://127.0.0.1:%d/json/list" % port, timeout=1).json()
                page = next(t for t in tabs if t.get("type") == "page")
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.25)
        report = asyncio.run(run(page["webSocketDebuggerUrl"], tokens, set(filter(None, args.only.split(",")))))
    finally:
        proc.terminate()
        proc.wait(timeout=10)
        shutil.rmtree(profile, ignore_errors=True)
    out = os.path.join(HERE, "audit.json")
    old = {}
    if os.path.exists(out):
        with io.open(out, encoding="utf-8") as f:
            old = json.load(f)
    old.update(report)
    with io.open(out, "w", encoding="utf-8") as f:
        json.dump(old, f, ensure_ascii=False, indent=1)
    print("寫好了：", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
