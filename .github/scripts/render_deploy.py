# -*- coding: utf-8 -*-
"""用 Render 的 API 部署，並把 Render 的 log **原封不動**印出來。

    python .github/scripts/render_deploy.py <服務名稱> <服務ID>

為什麼不用 Deploy Hook
======================================================================
Deploy Hook 只能「叫它部署」，打完就結束——部署成功沒成功、為什麼失敗，
都要進 Render 後台才看得到，而**後台只有那個 workspace 的成員進得去**。
四個人裡只有一個人有 Render 帳號的話，另外三個人等於看不到部署結果。

走 API 的話，這支程式會一邊等一邊把 Render 的 log 抓下來印出來。
印出來的東西進 GitHub Actions 的 log 與 Summary，那兩個地方是公開的，
所以**四個人不用 Render 帳號也看得到同一份 log**。

⚠️ 印出來的是 Render 回什麼就印什麼，不加前綴、不改字、不重排。
   要的就是「跟後台看到的一樣」，中間多一層加工就對不起來了。

需要的環境變數
======================================================================
    RENDER_API_KEY    Render 後台 → Account Settings → API Keys 產生
                      ⚠️ 等同你的 Render 帳號權限，只放 GitHub Secrets

怎麼找服務 ID
======================================================================
打開 Render 後台那個服務，網址長這樣：

    https://dashboard.render.com/web/srv-d1abc2de3fg4h5i6j7k0

最後那一段 srv-... 就是服務 ID。
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.render.com/v1"
KEY = os.environ.get("RENDER_API_KEY", "")
POLL_SECONDS = 5
GIVE_UP_AFTER = 20 * 60          # 20 分鐘。免費方案的 build 慢，但不該慢過這個

#: Render 的部署狀態：還在跑的 / 成功的 / 失敗的
RUNNING = ("created", "queued", "build_in_progress", "update_in_progress", "pre_deploy_in_progress")
GOOD = ("live",)

#: 收集起來的原始 log，最後要原樣貼進 Summary
COLLECTED = []


def out(line):
    """印出來，同時留一份給 Summary。"""
    COLLECTED.append(line)
    print(line, flush=True)


def call(method, path, body=None):
    req = urllib.request.Request(
        API + path,
        method=method,
        data=json.dumps(body).encode("utf-8") if body is not None else None,
        headers={
            "Authorization": "Bearer " + KEY,
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as res:
        raw = res.read().decode("utf-8")
    return json.loads(raw) if raw.strip() else {}


class LogTail:
    """把 Render 的 log 一段一段抓下來，只印沒印過的。

    ⚠️ 相鄰兩次查詢的時間區間會重疊（不重疊就會掉行），所以要自己去重。
       Render 同一毫秒可能有好幾行，光用時間戳當游標不夠。
    """

    def __init__(self, owner_id, service_id):
        self.owner_id = owner_id
        self.service_id = service_id
        self.seen = set()
        self.broken = False           # 這個方案拿不到 log 就別再試了

    def pull(self, limit=100):
        if self.broken or not self.owner_id:
            return
        q = urllib.parse.urlencode({
            "ownerId": self.owner_id,
            "resource": self.service_id,
            "limit": limit,
            "direction": "backward",
        })
        try:
            rows = (call("GET", "/logs?" + q) or {}).get("logs") or []
        except Exception as exc:                          # noqa: BLE001
            self.broken = True
            print("（這個方案的 API 拿不到 log：%s）" % exc, flush=True)
            return
        for row in reversed(rows):                        # 舊的先印
            key = (row.get("timestamp", ""), row.get("message", ""))
            if key in self.seen:
                continue
            self.seen.add(key)
            out(row.get("message", ""))                   # ← 原封不動，只印 message


def summary(service_id, status, ok):
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    dash = "https://dashboard.render.com/web/" + service_id
    with open(path, "a", encoding="utf-8") as fh:
        fh.write("### %s　`%s`\n\n" % ("部署成功" if ok else "部署失敗", status))
        if COLLECTED:
            fh.write("```\n" + "\n".join(COLLECTED) + "\n```\n\n")
        fh.write("Render 後台：%s\n\n" % dash)


def main():
    if len(sys.argv) != 3:
        print("用法：render_deploy.py <服務名稱> <服務ID>")
        return 2
    label, service_id = sys.argv[1], sys.argv[2]

    if not KEY:
        print("沒有 RENDER_API_KEY，跳過 %s。" % label)
        return 0

    service = call("GET", "/services/" + service_id)
    owner_id = service.get("ownerId") or ""
    tail = LogTail(owner_id, service_id)

    deploy = call("POST", "/services/%s/deploys" % service_id, {"clearCache": "do_not_clear"})
    did = deploy.get("id", "")
    status = deploy.get("status", "created")

    # 從這裡開始，印出來的都是 Render 自己的 log
    waited = 0
    while status in RUNNING and waited < GIVE_UP_AFTER:
        time.sleep(POLL_SECONDS)
        waited += POLL_SECONDS
        tail.pull()
        try:
            status = call("GET", "/services/%s/deploys/%s" % (service_id, did)).get("status", status)
        except urllib.error.URLError:
            continue                                      # 問不到就下一輪再問

    time.sleep(3)                                         # 最後幾行通常晚一點才進得去
    tail.pull()

    ok = status in GOOD
    summary(service_id, status, ok)
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    raise SystemExit(main())
