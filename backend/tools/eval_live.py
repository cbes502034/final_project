"""
線上評測：用已部署的後端（POST /api/nlp/parse-batch）跑留出集，量「上線那一套」的成績。

領域：記帳

跟 tools/eval_nlp.py 的差別：eval_nlp 在本機直接叫模型；這支打線上的 API，
所以量到的是「模型＋後處理（parse.postprocess、分類習慣）」整套上線的結果，結果檔格式一樣，
report/collect.py 會一起收進簡報。

    python tools/eval_live.py --token-file <只含 accessToken 的 JSON> --label claude-live

⚠️ 用一個沒有改過分類的帳號跑：改過的分類會套用「使用者習慣」，量到的就不只是模型。
⚠️ 線上的「今天」是伺服器跑的那一天：留出集的答案以 heldout 的 today 為準，這裡會換算到同一天
   （相對日期平移、星期幾用 toolkit/dates 重算、絕對日期不動）。
⚠️ 每一題呼叫一次線上模型（商業 API 會花錢，很少，但不是零）。
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone

import httpx

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(BACKEND)
sys.path.insert(0, BACKEND)
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("JWT_SECRET", "eval-only-not-a-real-secret-at-least-32-bytes")

from app.services import evaluation  # noqa: E402
from app.toolkit import dates  # noqa: E402

API = "https://fambudget-backend-tdvg.onrender.com"


def rebase(case: dict, today: str) -> list[dict]:
    """把答案的日期從留出集的 today 換到線上的 today。"""
    shift = date.fromisoformat(today) - date.fromisoformat(case["today"])
    out = []
    for g in case["items"]:
        d = g["date"]
        if "weekday" in case["tags"]:
            d = dates.find(case["text"], today) or (date.fromisoformat(d) + shift).isoformat()
        elif "abs-date" in case["tags"] and d != case["today"]:
            pass
        else:
            d = (date.fromisoformat(d) + shift).isoformat()
        out.append({**g, "date": d})
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="用線上的 API 跑留出集")
    ap.add_argument("--token-file", required=True, help="JSON：{\"accessToken\": \"…\"}（30 分鐘內有效）")
    ap.add_argument("--api", default=API)
    ap.add_argument("--set", default=os.path.join("eval", "heldout.jsonl"))
    ap.add_argument("--label", default="claude-live")
    ap.add_argument("--model", default="Claude（線上，含輸出檢查）")
    args = ap.parse_args()

    with io.open(args.token_file, encoding="utf-8") as f:
        token = json.load(f)["accessToken"]
    h = {"Authorization": "Bearer " + token}
    http = httpx.Client(base_url=args.api, headers=h, timeout=90)
    names = {str(c["id"]): c["name"] for c in http.get("/api/categories").json()["categories"]}
    today = datetime.now(timezone(timedelta(hours=8))).date().isoformat()

    with io.open(args.set, encoding="utf-8") as f:
        cases = [json.loads(line) for line in f if line.strip()]
    results = []
    for n, c in enumerate(cases, 1):
        t0 = time.perf_counter()
        r = http.post("/api/nlp/parse-batch", json={"text": c["text"]})
        seconds = round(time.perf_counter() - t0, 3)
        if r.status_code == 200:
            pred = [{"span": it["span"], "date": it["date"], "amount": it["amount"], "kind": it["kind"],
                     "cat": names.get(str(it["cat"])) if it["cat"] is not None else None} for it in r.json()["items"]]
            error = ""
        else:
            pred, error = [], "HTTP %d" % r.status_code
        results.append({"id": c["id"], "text": c["text"], "tags": c.get("tags", []), "gold": rebase(c, today),
                        "pred": pred, "seconds": seconds, "error": error})
        print("  %3d/%d  %s  %.1fs  %s" % (n, len(cases), c["id"], seconds, error), flush=True)

    report = evaluation.score(results)
    out = os.path.join("eval", "results", args.label + ".json")
    with io.open(out, "w", encoding="utf-8") as f:
        json.dump({"label": args.label, "model": args.model, "set": args.set,
                   "when": datetime.now().isoformat(timespec="seconds"),
                   "filters": {"api": args.api, "today": today, "dates": "答案日期換算到線上的今天"},
                   "report": report, "by_tag": evaluation.by_tag(results), "cases": results},
                  f, ensure_ascii=False, indent=1)
    print(evaluation.to_markdown({args.label: report}))
    print("結果存在 " + out)


if __name__ == "__main__":
    main()
