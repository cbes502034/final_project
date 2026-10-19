"""
展示用資料：在一台**本機**後端上建一個三口之家（林爸爸、林媽媽、林小華）與近三個月的帳。截圖、口頭報告現場展示用。

領域：認證（共用工具）

    python tools/demo_seed.py --base http://localhost:8010 --tokens <暫存資料夾>/demo_tokens.json
    # 平台管理頁也要截圖的話，給跟伺服器同一個 DATABASE_URL（才能把管理員帳號升級）：
    python tools/demo_seed.py --base http://localhost:8010 --tokens <…>/demo_tokens.json --db sqlite:///<…>/e2e.db

做了什麼：家庭與邀請碼、照看與零用金、兩本帳（家用、已結算的墾丁旅遊）、自訂分類、
近三個月的收支（含段落記帳來源）、預算、存款目標、提醒門檻。

給了 --db 再多一個平台管理員，以及管理頁會看到的事：有人連續猜錯林美玲的密碼（被鎖 15 分鐘）、
林小華的畫面回報了一個錯誤。

⚠️ 密碼每次隨機產生、不印出來；--tokens 寫出的是每個人的登入權杖（給瀏覽器直接登入截圖用），
   **只放暫存資料夾，不要 commit**。權杖過期就重跑一次。
⚠️ 只能對本機的後端跑，不要對正式站跑（會在正式資料庫裡建一堆假帳）。
"""

from __future__ import annotations

import argparse
import io
import json
import random
import secrets
import sys
from datetime import date, timedelta
from urllib.parse import urlparse

import httpx

#: (分類, 說法, 店家, 金額下限, 上限, 一個月幾筆)
SPEND = [
    ("餐飲", "早餐", "", 45, 120, 14), ("餐飲", "午餐", "", 90, 260, 12), ("餐飲", "晚餐", "", 150, 900, 8),
    ("餐飲", "咖啡", "路易莎", 60, 160, 6), ("交通", "加油", "中油", 600, 1500, 3), ("交通", "捷運", "", 30, 60, 6),
    ("日用品", "衛生紙洗衣精", "全聯", 250, 900, 3), ("居住", "電費", "", 1400, 2600, 1),
    ("居住", "網路費", "中華電信", 699, 699, 1), ("娛樂", "電影", "威秀", 560, 640, 1),
    ("醫療", "看診", "", 150, 450, 1), ("教育", "補習費", "", 4500, 4500, 1),
]


def main() -> int:
    ap = argparse.ArgumentParser(description="展示用資料")
    ap.add_argument("--base", default="http://localhost:8010")
    ap.add_argument("--tokens", required=True, help="登入權杖寫到這裡（暫存資料夾，不要 commit）")
    ap.add_argument("--db", default="", help="跟伺服器同一個 DATABASE_URL；給了才建平台管理員（升級要直接寫資料庫）")
    args = ap.parse_args()
    if urlparse(args.base).hostname not in ("localhost", "127.0.0.1"):
        sys.exit("只能對本機的後端跑")

    http = httpx.Client(base_url=args.base.rstrip("/"), timeout=60)
    rng = random.Random(1015)
    tag = secrets.token_hex(2)
    today = date.today()

    def call(method, path, token=None, **body):
        res = http.request(method, path, json=body or None,
                           headers={"authorization": "Bearer " + token} if token else {})
        if res.status_code >= 400:
            sys.exit("%s %s → %d %s" % (method, path, res.status_code, res.text[:200]))
        return res.json() if res.content else {}

    people = {}
    for who, name in (("dad", "林建宏"), ("mom", "林美玲"), ("kid", "林小華")):
        d = call("POST", "/api/auth/register", name=name, email="%s.%s@demo.test" % (who, tag),
                 password="demo-" + secrets.token_urlsafe(12))
        people[who] = d
    tok = {w: p["accessToken"] for w, p in people.items()}
    uid = {w: p["user"]["id"] for w, p in people.items()}

    for who in tok:                                                                  # 跳過註冊後的設定精靈
        call("PATCH", "/api/auth/me", tok[who], onboarded=True)
    call("PATCH", "/api/auth/me", tok["dad"], theme="sky")
    call("PUT", "/api/auth/me/finance", tok["dad"], style="balanced", goals=[], habits=[], note="希望每個月存一萬")
    call("POST", "/api/family", tok["dad"], name="林家")
    for who, role, label in (("mom", "parent", "給老婆"), ("kid", "child", "給小華")):
        code = call("POST", "/api/family/invite", tok["dad"], role=role, label=label)["code"]
        call("POST", "/api/family/join", tok[who], code=code)
    call("POST", "/api/family/invite", tok["dad"], role="parent", label="給阿嬤")      # 留一組沒用的，畫面上看得到
    call("POST", "/api/guardianships", tok["dad"], wardId=uid["kid"])
    call("PUT", "/api/allowance", tok["dad"], wardId=uid["kid"], amount=3000)

    cats = {c["name"]: c["id"] for c in call("GET", "/api/categories", tok["dad"])["categories"]}
    pet = call("POST", "/api/categories", tok["dad"], name="寵物", kind="expense")
    cats["寵物"] = pet.get("id") or pet.get("category", {}).get("id")

    def group(token, **body):
        g = call("POST", "/api/groups", token, **body)
        return g.get("id") or g.get("group", {}).get("id")

    home = group(tok["dad"], name="家用")
    call("POST", "/api/groups/%s/members" % home, tok["dad"], userId=uid["mom"])
    mom_book = group(tok["mom"], name="媽媽的帳")
    kid_book = group(tok["kid"], name="零用錢")

    def tx(token, day, amount, kind, cat, gid, merchant="", note=""):
        call("POST", "/api/transactions", token, date=day.isoformat(), amount=amount, kind=kind,
             cat=cats[cat], groupId=gid, merchant=merchant, note=note)

    first = today.replace(day=1)
    months = [first]
    for _ in range(2):
        months.insert(0, (months[0] - timedelta(days=1)).replace(day=1))
    n = 0
    for m in months:
        last = today if m == first else (m.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        days = (last - m).days + 1
        tx(tok["dad"], m + timedelta(days=min(4, days - 1)), 62000, "income", "薪資", home, note="薪水")
        tx(tok["mom"], m + timedelta(days=min(4, days - 1)), 41000, "income", "薪資", mom_book, note="薪水")
        for cat, note, merchant, lo, hi, per in SPEND:
            count = max(1, round(per * days / 30))
            for _ in range(count):
                amount = rng.randint(lo, hi) if lo != hi else lo
                amount = round(amount, -1) if amount > 100 else amount
                who = rng.choice(["dad", "dad", "mom"])
                tx(tok[who], m + timedelta(days=rng.randrange(days)), amount, "expense", cat,
                   home if who == "dad" else mom_book, merchant, note)
                n += 1
        tx(tok["dad"], m + timedelta(days=rng.randrange(days)), 680, "expense", "寵物", home, "寵物公園", "飼料")
        for _ in range(4):
            tx(tok["kid"], m + timedelta(days=rng.randrange(days)), rng.choice([60, 85, 120, 150, 299]),
               "expense", rng.choice(["餐飲", "娛樂", "教育"]), kid_book, "", "零用錢")
    # 這個月用段落記帳記的兩筆
    call("POST", "/api/nlp/confirm-batch", tok["dad"], raw="早上買早餐55，晚上加油1200", items=[
        {"span": "早上買早餐55", "date": today.isoformat(), "amount": 55, "kind": "expense", "cat": cats["餐飲"],
         "note": "早餐", "groupId": home, "conf": {"date": 0.95, "amount": 0.98, "kind": 0.97, "cat": 0.93}},
        {"span": "晚上加油1200", "date": today.isoformat(), "amount": 1200, "kind": "expense", "cat": cats["交通"],
         "note": "加油", "groupId": home, "conf": {"date": 0.95, "amount": 0.98, "kind": 0.96, "cat": 0.9}}])

    trip = group(tok["dad"], name="墾丁三天兩夜", kind="temp", endsOn=(today + timedelta(days=2)).isoformat())
    for amount, cat, note in ((3600, "居住", "民宿"), (1880, "餐飲", "海鮮"), (960, "交通", "租機車")):
        tx(tok["dad"], today - timedelta(days=rng.randint(10, 20)), amount, "expense", cat, trip, "", note)
    call("POST", "/api/groups/%s/settle" % trip, tok["dad"])

    call("PUT", "/api/budgets", tok["dad"], cat=cats["餐飲"], limit=9000)
    call("PUT", "/api/budgets", tok["dad"], cat=cats["交通"], limit=3000)
    call("PUT", "/api/budgets", tok["dad"], cat=cats["娛樂"], limit=1500)
    call("PUT", "/api/savings-goal", tok["dad"], userId=uid["dad"], goal=10000)
    call("POST", "/api/alerts", tok["dad"], percent=50)
    call("POST", "/api/alerts", tok["dad"], percent=80)
    call("GET", "/api/notifications", tok["dad"])                                    # 讓提醒門檻寫進通知

    if args.db:
        # 平台管理員：先註冊，再用 make-admin 升級（跟正式環境的 ADMIN_EMAILS 同一條路）
        import os
        import subprocess
        backend = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        mail = "admin.%s@demo.test" % tag
        pw = "demo-" + secrets.token_urlsafe(12)
        call("POST", "/api/auth/register", name="平台管理員", email=mail, password=pw)
        subprocess.run([sys.executable, "-m", "app.cli", "make-admin", mail], cwd=backend, check=True,
                       env=dict(os.environ, DATABASE_URL=args.db), capture_output=True)
        people["admin"] = call("POST", "/api/auth/login", email=mail, password=pw)
        # 管理頁會看到的事：有人連續猜錯林美玲的密碼、林小華的畫面回報了一個錯誤
        for _ in range(5):
            http.post("/api/auth/login", json={"email": "mom.%s@demo.test" % tag, "password": "wrong-password"})
        http.post("/api/client-errors", headers={"authorization": "Bearer " + tok["kid"]},
                  json={"message": "Cannot read properties of undefined (reading 'map')",
                        "location": "vStats（app.js）", "page": "#/stats"})
        call("GET", "/api/auth/me", tok["kid"])

    with io.open(args.tokens, "w", encoding="utf-8") as f:
        json.dump({w: {"accessToken": p["accessToken"], "refreshToken": p["refreshToken"],
                       "expiresIn": p["expiresIn"]} for w, p in people.items()}, f)
    print("建好了：林家三個人%s、%d 筆支出、3 本帳。權杖寫在 %s（不要 commit）"
          % ("＋平台管理員" if args.db else "", n, args.tokens))
    return 0


if __name__ == "__main__":
    sys.exit(main())
