"""
端到端測試：對一台**真的在跑**的後端，用 HTTP 把四個領域的主要流程走一遍，結果存成 JSON（報告的測試章節用）。

領域：認證（共用工具）

    # 1. 開一個乾淨的資料庫與後端（在 backend/ 底下；不會碰你原本的資料庫）
    set DATABASE_URL=sqlite:///e2e.db&& set ADMIN_EMAILS=admin@e2e.test&& python -m app.cli init-db
    set DATABASE_URL=sqlite:///e2e.db&& set ADMIN_EMAILS=admin@e2e.test&& uvicorn app.main:app --port 8010
    # 2. 另一個視窗
    python tools/e2e_check.py --base http://localhost:8010 --db sqlite:///e2e.db

跟 pytest 的差別：pytest 在記憶體裡直接呼叫函式；這支走真的網路、真的伺服器、真的資料庫檔，
測的是「部署起來之後整套能不能用」。

⚠️ 帳號與密碼是每次隨機產生的測試值，不會印出來、也不會存。
⚠️ 模型沒設定時，段落解析與財務建議預期是 503（前端會用規則頂著）；設定了預期是 200／201。
"""

from __future__ import annotations

import argparse
import io
import json
import os
import secrets
import subprocess
import sys
import time
from datetime import date, timedelta

import httpx

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Run:
    def __init__(self, base: str):
        self.http = httpx.Client(base_url=base.rstrip("/"), timeout=120)
        self.rows: list[dict] = []
        self.domain = ""

    def step(self, name, method, path, *, token=None, want=(200,), json_body=None, check=None):
        """送一個請求；狀態碼在 want 裡、check 也通過才算過。回傳 (回應的 JSON 或 None, 有沒有過)。"""
        headers = {"authorization": "Bearer " + token} if token else {}
        t0 = time.perf_counter()
        try:
            res = self.http.request(method, path, headers=headers, json=json_body)
            status = res.status_code
            try:
                data = res.json()
            except ValueError:
                data = None
        except httpx.HTTPError as exc:
            status, data = 0, {"detail": exc.__class__.__name__}
        ms = round((time.perf_counter() - t0) * 1000)
        ok = status in want
        note = ""
        if ok and check:
            try:
                result = check(data)
                ok = result is not False
                note = result if isinstance(result, str) else ""
            except Exception as exc:  # noqa: BLE001  檢查本身壞掉也算沒過，而且要看得到原因
                ok, note = False, "檢查失敗：%r" % exc
        if not ok and not note:
            note = str((data or {}).get("detail", ""))[:120] if isinstance(data, dict) else ""
        self.rows.append({"domain": self.domain, "name": name, "method": method, "path": path.split("?")[0],
                          "want": list(want), "got": status, "ok": ok, "ms": ms, "note": note})
        print("  %s %-34s %s %s → %s %s" % ("✓" if ok else "✗", name, method, path.split("?")[0], status, note),
              flush=True)
        return data, ok


def new_password() -> str:
    return "e2e-" + secrets.token_urlsafe(12)


def main() -> int:
    ap = argparse.ArgumentParser(description="端到端測試")
    ap.add_argument("--base", default="http://localhost:8010")
    ap.add_argument("--db", default="", help="跟伺服器同一個 DATABASE_URL；給了才會把管理員帳號升級成平台管理員")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(BACKEND), "report", "data", "e2e.json"))
    args = ap.parse_args()

    r = Run(args.base)
    tag = secrets.token_hex(3)
    today = date.today()
    pw = {k: new_password() for k in ("dad", "kid", "mom", "out", "admin")}
    mail = {k: "%s.%s@e2e.test" % (k, tag) for k in pw}
    mail["admin"] = "admin@e2e.test"
    tok: dict[str, str] = {}
    refresh: dict[str, str] = {}
    uid: dict[str, str] = {}

    # ------------------------------------------------------------------ 認證
    r.domain = "認證"
    for who, name in (("dad", "林爸爸"), ("kid", "林小華"), ("mom", "林媽媽"), ("out", "路人"), ("admin", "管理員")):
        # 註冊完不登入（要先點驗證信）；本機沒設寄信，直接算驗證過，下面登入就好
        r.step("註冊：" + name, "POST", "/api/auth/register", want=(201, 409),
               json_body={"name": name, "email": mail[who], "password": pw[who]},
               check=lambda d: "accessToken" not in d)
    if args.db:
        env = dict(os.environ, DATABASE_URL=args.db, ADMIN_EMAILS=mail["admin"])
        subprocess.run([sys.executable, "-m", "app.cli", "make-admin"], cwd=BACKEND, env=env,
                       capture_output=True, check=False)
    r.step("密碼打錯會被擋", "POST", "/api/auth/login", want=(401,),
           json_body={"email": mail["dad"], "password": "wrong-password-1"})
    for who in pw:
        data, ok = r.step("登入：" + who, "POST", "/api/auth/login",
                          json_body={"email": mail[who], "password": pw[who]})
        if ok:
            tok[who], refresh[who], uid[who] = data["accessToken"], data["refreshToken"], data["user"]["id"]
    r.step("讀自己的資料", "GET", "/api/auth/me", token=tok["dad"],
           check=lambda d: d["user"]["name"] == "林爸爸" if "user" in d else d.get("name") == "林爸爸")
    r.step("改主題", "PATCH", "/api/auth/me", token=tok["dad"], json_body={"theme": "sky"})
    r.step("填理財習慣", "PUT", "/api/auth/me/finance", token=tok["dad"],
           json_body={"style": "safe", "goals": [], "habits": [], "note": "想多存一點"})
    data, ok = r.step("用 refresh 換新的 access", "POST", "/api/auth/refresh", json_body={"refreshToken": refresh["dad"]})
    if ok:
        tok["dad"], refresh["dad"] = data["accessToken"], data.get("refreshToken", refresh["dad"])
    r.step("看登入中的裝置", "GET", "/api/auth/sessions", token=tok["dad"])
    r.step("敏感操作前再確認密碼", "POST", "/api/auth/verify-password", token=tok["dad"],
           json_body={"password": pw["dad"]})
    r.step("沒登入打 API 會被擋", "GET", "/api/transactions", want=(401,))

    # ------------------------------------------------------------------ 家庭
    r.domain = "家庭"
    r.step("建立家庭", "POST", "/api/family", token=tok["dad"], want=(201,), json_body={"name": "林家"})
    code_kid, _ = r.step("產生邀請碼（子女）", "POST", "/api/family/invite", token=tok["dad"], want=(201,),
                         json_body={"role": "child", "label": "給小華"}, check=lambda d: bool(d.get("code")))
    r.step("子女用邀請碼加入", "POST", "/api/family/join", token=tok["kid"], want=(200, 201),
           json_body={"code": (code_kid or {}).get("code", "")})
    r.step("同一個邀請碼不能再用", "POST", "/api/family/join", token=tok["out"], want=(400, 404, 409, 410),
           json_body={"code": (code_kid or {}).get("code", "")})
    wasted, _ = r.step("產生邀請碼（要刪掉的）", "POST", "/api/family/invite", token=tok["dad"], want=(201,),
                       json_body={"role": "parent", "label": "打錯的"})
    r.step("邀請碼清單看得到標題", "GET", "/api/family/invites", token=tok["dad"],
           check=lambda d: "打錯的" in json.dumps(d, ensure_ascii=False))
    r.step("刪掉沒用過的邀請碼", "DELETE", "/api/family/invites/%s" % (wasted or {}).get("id", "0"),
           token=tok["dad"], want=(200, 204))
    r.step("刪掉的邀請碼不能用", "POST", "/api/family/join", token=tok["mom"], want=(400, 404, 409, 410),
           json_body={"code": (wasted or {}).get("code", "")})
    code_mom, _ = r.step("產生邀請碼（家長）", "POST", "/api/family/invite", token=tok["dad"], want=(201,),
                         json_body={"role": "parent", "label": "給媽媽"})
    r.step("家長用邀請碼加入", "POST", "/api/family/join", token=tok["mom"], want=(200, 201),
           json_body={"code": (code_mom or {}).get("code", "")})
    r.step("家庭有三個人", "GET", "/api/family", token=tok["dad"],
           check=lambda d: len((d.get("family") or d).get("members", d.get("members", []))) == 3
           if isinstance(d, dict) else False)
    r.step("用 email 找人", "GET", "/api/family/lookup?email=" + mail["out"], token=tok["dad"])
    r.step("子女不能找人", "GET", "/api/family/lookup?email=" + mail["out"], token=tok["kid"], want=(403,))
    r.step("家長照看子女", "POST", "/api/guardianships", token=tok["dad"], want=(200, 201),
           json_body={"wardId": uid["kid"]})
    r.step("子女不能照看別人", "POST", "/api/guardianships", token=tok["kid"], want=(403,),
           json_body={"wardId": uid["kid"]})
    r.step("設零用金", "PUT", "/api/allowance", token=tok["dad"], json_body={"wardId": uid["kid"], "amount": 3000})
    r.step("看零用金", "GET", "/api/allowances", token=tok["dad"])

    # ------------------------------------------------------------------ 記帳
    r.domain = "記帳"
    cats, _ = r.step("分類清單", "GET", "/api/categories", token=tok["dad"],
                     check=lambda d: len(d.get("categories", d)) >= 12)
    by_name = {c["name"]: c["id"] for c in (cats or {}).get("categories", [])}
    pet, _ = r.step("新增家庭自訂分類", "POST", "/api/categories", token=tok["dad"], want=(201,),
                    json_body={"name": "寵物", "kind": "expense"})
    pet_id = (pet or {}).get("id") or ((pet or {}).get("category") or {}).get("id")
    g, _ = r.step("建一本帳", "POST", "/api/groups", token=tok["dad"], want=(201,), json_body={"name": "家用"})
    gid = (g or {}).get("id") or ((g or {}).get("group") or {}).get("id")
    r.step("把媽媽加進帳本", "POST", "/api/groups/%s/members" % gid, token=tok["dad"], want=(200, 201),
           json_body={"userId": uid["mom"]})
    d0 = today.isoformat()
    sal, _ = r.step("記一筆收入（薪水）", "POST", "/api/transactions", token=tok["dad"], want=(201,),
                    json_body={"date": d0, "amount": 50000, "kind": "income", "cat": by_name.get("薪資", ""),
                               "groupId": gid})
    food, _ = r.step("記一筆支出（餐飲）", "POST", "/api/transactions", token=tok["dad"], want=(201,),
                     json_body={"date": d0, "amount": 8600, "kind": "expense", "cat": by_name.get("餐飲", ""),
                                "merchant": "全聯", "groupId": gid})
    r.step("收支對不上的分類會被擋", "POST", "/api/transactions", token=tok["dad"], want=(400, 422),
           json_body={"date": d0, "amount": 10, "kind": "expense", "cat": by_name.get("薪資", ""), "groupId": gid})
    gk, _ = r.step("子女建自己的帳本", "POST", "/api/groups", token=tok["kid"], want=(201,), json_body={"name": "零用錢"})
    gkid = (gk or {}).get("id") or ((gk or {}).get("group") or {}).get("id")
    r.step("子女記一筆", "POST", "/api/transactions", token=tok["kid"], want=(201,),
           json_body={"date": d0, "amount": 120, "kind": "expense", "cat": by_name.get("娛樂", ""), "groupId": gkid})
    notes, _ = r.step("家長收到子女記帳的通知", "GET", "/api/notifications", token=tok["dad"],
                      check=lambda d: "ward_transaction" in json.dumps(d))
    newest = max((n["id"] for n in (notes or {}).get("notifications", [])), key=int, default="0")
    r.step("通知全部標已讀（只標到按下去當時最新那一則）", "PATCH", "/api/notifications", token=tok["dad"],
           json_body={"readUntil": newest})
    r.step("收支明細", "GET", "/api/transactions", token=tok["dad"],
           check=lambda d: len(d.get("transactions", [])) >= 2)
    r.step("家長看得到照看的子女的帳", "GET", "/api/transactions?userId=%s" % uid["kid"], token=tok["dad"],
           check=lambda d: len(d.get("transactions", [])) >= 1)
    r.step("子女看不到家長的帳", "GET", "/api/transactions?userId=%s" % uid["dad"], token=tok["kid"], want=(403,))
    fid = (food or {}).get("id") or ((food or {}).get("transaction") or {}).get("id")
    r.step("改一筆的備註", "PATCH", "/api/transactions/%s" % fid, token=tok["dad"], json_body={"note": "一週的菜"})
    r.step("外人不能改別人的帳", "PATCH", "/api/transactions/%s" % fid, token=tok["out"], want=(403, 404),
           json_body={"note": "x"})
    tmp, _ = r.step("記一筆等等要刪的", "POST", "/api/transactions", token=tok["dad"], want=(201,),
                    json_body={"date": d0, "amount": 1, "kind": "expense", "cat": by_name.get("其他", ""),
                               "groupId": gid})
    tid = (tmp or {}).get("id") or ((tmp or {}).get("transaction") or {}).get("id")
    r.step("刪一筆", "DELETE", "/api/transactions/%s" % tid, token=tok["dad"], want=(200, 204))
    trip, _ = r.step("建活動帳本（有結束日）", "POST", "/api/groups", token=tok["dad"], want=(201,),
                     json_body={"name": "墾丁", "kind": "temp", "endsOn": (today + timedelta(days=3)).isoformat()})
    trip_id = (trip or {}).get("id") or ((trip or {}).get("group") or {}).get("id")
    r.step("結算活動帳本", "POST", "/api/groups/%s/settle" % trip_id, token=tok["dad"], want=(200,))
    r.step("結算後不能再記", "POST", "/api/transactions", token=tok["dad"], want=(400, 403, 409, 422),
           json_body={"date": d0, "amount": 100, "kind": "expense", "cat": by_name.get("餐飲", ""),
                      "groupId": trip_id})
    parsed, ok = r.step("段落解析", "POST", "/api/nlp/parse-batch", token=tok["dad"], want=(200, 503),
                        json_body={"text": "早上買早餐55，中午吃飯120，晚上加油1200"})
    r.rows[-1]["note"] = "模型解析，切成 %d 筆" % len(parsed["items"]) if r.rows[-1]["got"] == 200 else \
        "503：模型沒設定，前端改用規則（預期）"
    r.step("段落確認寫入（全部成功或全部不寫）", "POST", "/api/nlp/confirm-batch", token=tok["dad"], want=(200, 201),
           json_body={"items": [
               {"span": "早上買早餐55", "date": d0, "amount": 55, "kind": "expense", "cat": by_name.get("餐飲", ""),
                "note": "早餐", "groupId": gid, "conf": {"date": 0.9, "amount": 0.9, "kind": 0.9, "cat": 0.9}},
               {"span": "晚上加油1200", "date": d0, "amount": 1200, "kind": "expense", "cat": by_name.get("交通", ""),
                "note": "加油", "groupId": gid, "conf": {"date": 0.9, "amount": 0.9, "kind": 0.9, "cat": 0.9}}],
               "raw": "早上買早餐55，晚上加油1200"})

    # ------------------------------------------------------------------ 數字
    r.domain = "數字"
    r.step("這個月的總覽數字", "GET", "/api/summary", token=tok["dad"],
           check=lambda d: float(d["income"]) == 50000 and float(d["expense"]) == 8600 + 55 + 1200)
    r.step("子女看全家（只算得到自己看得到的）", "GET", "/api/summary?scope=family", token=tok["kid"], want=(200, 403))
    r.step("家長看全家", "GET", "/api/summary?scope=family", token=tok["dad"])
    r.step("設分類預算", "PUT", "/api/budgets", token=tok["dad"], want=(200, 201),
           json_body={"cat": by_name.get("餐飲", ""), "limit": 8000})
    r.step("預算使用狀況", "GET", "/api/budgets", token=tok["dad"],
           check=lambda d: any(float(b.get("limit", 0)) == 8000 for b in d.get("budgets", [])))
    r.step("設存款目標", "PUT", "/api/savings-goal", token=tok["dad"], want=(200, 201),
           json_body={"userId": uid["dad"], "goal": 10000})
    r.step("存款目標清單", "GET", "/api/savings-goals", token=tok["dad"])
    al, _ = r.step("設提醒門檻 20%", "POST", "/api/alerts", token=tok["dad"], want=(201,), json_body={"percent": 20})
    r.step("跨過門檻收到提醒", "GET", "/api/notifications", token=tok["dad"],
           check=lambda d: "budget_alert" in json.dumps(d))
    aid = (al or {}).get("id") or ((al or {}).get("alert") or {}).get("id")
    r.step("停用提醒", "PATCH", "/api/alerts/%s" % aid, token=tok["dad"], json_body={"enabled": False})
    r.step("刪除提醒", "DELETE", "/api/alerts/%s" % aid, token=tok["dad"], want=(200, 204))
    adv, _ = r.step("產生財務建議", "POST", "/api/advices/generate", token=tok["dad"], want=(201, 503),
                    json_body={"scope": "me"})
    r.rows[-1]["note"] = "模型寫了 %d 則" % len(adv["advices"]) if r.rows[-1]["got"] == 201 else \
        "503：模型沒設定，前端用同一批數字寫（預期）"
    advs, _ = r.step("財務建議清單", "GET", "/api/advices", token=tok["dad"])

    # ------------------------------------------------------------------ 刪除（登記的資料都要能刪）
    first = next(iter((advs or {}).get("advices", [])), None)
    if first:
        r.step("刪一則建議", "DELETE", "/api/advices/%s" % first["id"], token=tok["dad"],
               check=lambda d: d.get("deleted") is True)
    r.step("別人的、找不到的建議刪不到（404）", "DELETE", "/api/advices/999999", token=tok["dad"], want=(404,))
    r.domain = "記帳"
    r.step("記一筆寵物的帳", "POST", "/api/transactions", token=tok["dad"], want=(201,),
           json_body={"date": d0, "amount": 300, "kind": "expense", "cat": pet_id, "groupId": gid})
    r.step("子女不能刪家庭的分類", "DELETE", "/api/categories/%s" % pet_id, token=tok["kid"], want=(403,))
    r.step("刪自訂分類：用它記的帳改到「其他」", "DELETE", "/api/categories/%s" % pet_id, token=tok["dad"],
           check=lambda d: d.get("deleted") is True and int(d.get("moved", 0)) == 1)
    r.domain = "家庭"
    nl, _ = r.step("通知清單", "GET", "/api/notifications", token=tok["dad"])
    nid = next(iter(n["id"] for n in (nl or {}).get("notifications", [])), "0")
    r.step("刪通知沒帶 ids 一定 400（不會被當成全部刪光）", "DELETE", "/api/notifications", token=tok["dad"], want=(400,))
    r.step("刪一則通知", "DELETE", "/api/notifications?ids=%s" % nid, token=tok["dad"],
           check=lambda d: d.get("deleted") == [nid])

    # ------------------------------------------------------------------ 平台管理員
    r.domain = "認證"
    if args.db:
        data, ok = r.step("管理員重新登入", "POST", "/api/auth/login",
                          json_body={"email": mail["admin"], "password": pw["admin"]})
        if ok:
            tok["admin"] = data["accessToken"]
        r.step("管理員看使用者清單", "GET", "/api/admin/users", token=tok["admin"])
        r.step("管理員讀不到任何人的帳", "GET", "/api/transactions", token=tok["admin"], want=(403,))
        r.step("一般使用者不能進管理頁", "GET", "/api/admin/users", token=tok["dad"], want=(403,))
        r.step("管理員停權路人", "POST", "/api/admin/users/%s/suspend" % uid["out"], token=tok["admin"],
               want=(200,), json_body={"reason": "端到端測試"})
        r.step("停權的人登入不了", "POST", "/api/auth/login", want=(401, 403),
               json_body={"email": mail["out"], "password": pw["out"]})
        r.step("解除停權", "DELETE", "/api/admin/users/%s/suspend" % uid["out"], token=tok["admin"], want=(200,))
        back, ok = r.step("解除後登得進去", "POST", "/api/auth/login", json_body={"email": mail["out"], "password": pw["out"]})
        if ok:
            tok["out"] = back["accessToken"]          # 停權時舊的登入都被撤掉了
    other, _ = r.step("媽媽在第二台裝置登入", "POST", "/api/auth/login",
                      json_body={"email": mail["mom"], "password": pw["mom"]})
    r.step("改密碼", "PATCH", "/api/auth/password", token=tok["mom"],
           json_body={"oldPassword": pw["mom"], "newPassword": new_password()})
    r.step("改密碼後其他裝置被登出", "POST", "/api/auth/refresh", want=(401,),
           json_body={"refreshToken": (other or {}).get("refreshToken", "")})
    r.step("改密碼的這一台不受影響", "POST", "/api/auth/refresh", json_body={"refreshToken": refresh["mom"]})
    r.step("登出", "POST", "/api/auth/logout", token=tok["dad"], want=(200, 204),
           json_body={"refreshToken": refresh["dad"]})
    r.step("登出後 refresh 不能用", "POST", "/api/auth/refresh", want=(401,), json_body={"refreshToken": refresh["dad"]})
    r.step("還在家庭裡不能刪帳號", "DELETE", "/api/auth/me", token=tok["kid"], want=(409,))
    r.step("路人刪除自己的帳號", "DELETE", "/api/auth/me", token=tok["out"], check=lambda d: d.get("deleted") is True)
    r.step("刪掉的帳號登不進去", "POST", "/api/auth/login", want=(401,),
           json_body={"email": mail["out"], "password": pw["out"]})

    passed = sum(row["ok"] for row in r.rows)
    print("\n%d / %d 通過" % (passed, len(r.rows)))
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with io.open(args.out, "w", encoding="utf-8") as f:
        json.dump({"when": time.strftime("%Y-%m-%d %H:%M"), "base": args.base, "passed": passed,
                   "total": len(r.rows), "steps": r.rows}, f, ensure_ascii=False, indent=1)
    print("結果存在 " + args.out)
    return 0 if passed == len(r.rows) else 1


if __name__ == "__main__":
    sys.exit(main())
