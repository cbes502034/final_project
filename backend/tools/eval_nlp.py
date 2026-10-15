"""
記帳解析的評測：用留出集（eval/heldout.jsonl）量模型的成績，結果存成 JSON、印成 Markdown 表。

領域：記帳

在 backend/ 底下跑（會讀 backend/.env 的模型設定）：

    python tools/eval_nlp.py --limit 5                 # 先跑 5 題，確認模型接得上
    python tools/eval_nlp.py --label claude            # 整份留出集 → eval/results/claude.json
    python tools/eval_nlp.py --rules                   # 基準線：前端的規則解析（不花錢，要裝 node）
    python tools/eval_nlp.py --only multi              # 只跑某一種題目（tags：multi、zh-num、rel-date…）
    python tools/eval_nlp.py --compare eval/results/rules.json eval/results/claude.json
                                                       # 幾次的結果排成一張表，直接貼進報告

⚠️ 中斷了（關掉視窗、電腦睡著）沒關係：每跑完一題就存進 eval/results/<label>.partial.jsonl，
   同一個 --label 再跑一次會從沒跑過的那題接下去。
⚠️ 會真的呼叫模型：整份留出集約 100 次。商業 API 會花錢（很少，但不是零），先用 --limit 試。
⚠️ 想比「零樣本 vs 我們微調的模型」：把 backend/.env 的 MODEL_* 換成另一組，換一個 --label 再跑一次。
"""

from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
import time
from datetime import datetime

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(BACKEND)
os.chdir(BACKEND)                                         # backend/.env 才讀得到
sys.path.insert(0, BACKEND)
os.environ.setdefault("DATABASE_URL", "sqlite://")        # 評測不碰資料庫，只是讓設定檔載得起來
os.environ.setdefault("JWT_SECRET", "eval-only-not-a-real-secret-at-least-32-bytes")

from app import catalog  # noqa: E402
from app.services import evaluation  # noqa: E402
from app.services.llm import client, parse  # noqa: E402

#: 跟 python -m app.cli init-db 放進去的順序一樣，id 從 1 開始
CATEGORIES = [{"id": str(i + 1), "name": n, "kind": k} for i, (n, k, _c, _i) in enumerate(catalog.SYSTEM_CATEGORIES)]
NAMES = {c["id"]: c["name"] for c in CATEGORIES}


def load(path: str) -> list[dict]:
    with io.open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def run_model(cases: list[dict], pause: float, partial: str) -> list[dict]:
    """一題一題跑，每跑完一題就寫進 partial（.partial.jsonl）。中斷了再跑一次會從沒跑過的那題接下去。"""
    done = {}
    if os.path.exists(partial):
        with io.open(partial, encoding="utf-8") as f:
            done = {r["id"]: r for r in map(json.loads, filter(str.strip, f))}
        print("  接續上次：已經有 %d 題" % len(done), flush=True)
    out = []
    for n, c in enumerate(cases, 1):
        if c["id"] in done:
            out.append(done[c["id"]])
            continue
        t0 = time.perf_counter()
        try:
            res = parse.parse_batch(c["text"], CATEGORIES, c["today"])
            pred = [{"span": it["span"], "date": it["date"], "amount": it["amount"], "kind": it["kind"],
                     "cat": NAMES.get(str(it["cat"])) if it["cat"] is not None else None} for it in res["items"]]
            error = ""
        except client.ModelError as exc:
            pred, error = [], str(exc)
        seconds = round(time.perf_counter() - t0, 3)
        out.append({**_head(c), "pred": pred, "seconds": seconds, "error": error})
        with io.open(partial, "a", encoding="utf-8") as f:
            f.write(json.dumps(out[-1], ensure_ascii=False) + "\n")
        print("  %3d/%d  %s  %.1fs  %s" % (n, len(cases), c["id"], seconds, error or ""), flush=True)
        if pause:
            time.sleep(pause)
    return out


def run_rules(cases: list[dict], path: str) -> list[dict]:
    script = os.path.join(BACKEND, "tools", "rules_baseline.js")
    try:
        res = subprocess.run(["node", script, REPO, path], capture_output=True, text=True, encoding="utf-8",
                             check=True)
    except FileNotFoundError:
        sys.exit("找不到 node。規則基準線要用 node 跑前端的 api.js：https://nodejs.org/")
    except subprocess.CalledProcessError as exc:
        sys.exit("規則解析跑失敗：\n" + exc.stderr)
    preds = {r["id"]: r["items"] for r in map(json.loads, filter(None, res.stdout.splitlines()))}
    wanted = {c["id"] for c in cases}
    return [{**_head(c), "pred": preds.get(c["id"], []), "seconds": None, "error": ""}
            for c in load(path) if c["id"] in wanted]


def _head(c: dict) -> dict:
    return {"id": c["id"], "text": c["text"], "tags": c.get("tags", []), "gold": c["items"]}


def show_misses(cases: list[dict], limit: int = 15) -> None:
    """錯在哪裡：報告的「錯誤分析」從這裡挑例子。"""
    shown = 0
    for c in cases:
        rep = evaluation.score([c])
        if rep["case_exact"] == 1:
            continue
        shown += 1
        if shown > limit:
            print("  ……還有更多，完整的在輸出的 JSON 裡")
            break
        print("  [%s] %s" % (c["id"], c["text"]))
        if c["error"]:
            print("      叫不動：" + c["error"])
            continue
        for p, g in evaluation.match_items(c["pred"], c["gold"]):
            wrong = [f for f in evaluation.FIELDS if not evaluation.same(f, (p or {}).get(f), (g or {}).get(f))]
            if wrong:
                print("      %s → 模型 %s／答案 %s" % ("、".join(wrong),
                      {f: (p or {}).get(f) for f in wrong} if p else "（漏掉）",
                      {f: (g or {}).get(f) for f in wrong} if g else "（多切的）"))


def main() -> None:
    ap = argparse.ArgumentParser(description="記帳解析的評測")
    ap.add_argument("--set", default=os.path.join("eval", "heldout.jsonl"), help="留出集（預設 eval/heldout.jsonl）")
    ap.add_argument("--rules", action="store_true", help="跑前端的規則解析（基準線）")
    ap.add_argument("--limit", type=int, default=0, help="只跑前 N 題")
    ap.add_argument("--only", default="", help="只跑帶這個 tag 的題目")
    ap.add_argument("--label", default="", help="這次結果的名稱（輸出檔名、表格欄名）")
    ap.add_argument("--out", default="", help="輸出 JSON 的路徑（預設 eval/results/<label>.json）")
    ap.add_argument("--pause", type=float, default=0.0, help="每題之間停幾秒（遇到 429 時用）")
    ap.add_argument("--compare", nargs="+", default=None, help="把幾個結果 JSON 排成一張表")
    args = ap.parse_args()

    if args.compare:
        reports = {}
        for path in args.compare:
            with io.open(path, encoding="utf-8") as f:
                data = json.load(f)
            reports[data["label"]] = data["report"]
        print(evaluation.to_markdown(reports))
        return

    cases = load(args.set)
    if args.only:
        cases = [c for c in cases if args.only in c.get("tags", [])]
    if args.limit:
        cases = cases[: args.limit]
    if not cases:
        sys.exit("沒有題目可以跑")

    if args.rules:
        label = args.label or "rules"
        print("規則基準線：%d 題" % len(cases))
        results = run_rules(cases, args.set)
        model = "frontend rules (api.js parseLine)"
    else:
        if not client.is_configured():
            sys.exit("backend/.env 的模型服務還沒設定（MODEL_PROVIDER、MODEL_API_KEY／MODEL_BASE_URL），"
                     "見 docs/03-LLM實作規劃.md")
        model = client.model_name()
        label = args.label or model
        print("模型 %s（%s）：%d 題，會呼叫模型 %d 次" % (model, client._cfg("parse")["provider"], len(cases), len(cases)))

    out = args.out or os.path.join("eval", "results", label + ".json")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    partial = os.path.splitext(out)[0] + ".partial.jsonl"
    if not args.rules:
        results = run_model(cases, args.pause, partial)

    report = evaluation.score(results)
    unchecked = sum(1 for c in load(args.set) if not c.get("checked"))
    with io.open(out, "w", encoding="utf-8") as f:
        json.dump({"label": label, "model": model, "set": args.set, "when": datetime.now().isoformat(timespec="seconds"),
                   "filters": {"only": args.only, "limit": args.limit}, "report": report,
                   "by_tag": evaluation.by_tag(results), "cases": results}, f, ensure_ascii=False, indent=1)
    if os.path.exists(partial):
        os.remove(partial)                     # 整份跑完了，接續用的暫存檔不用留

    print()
    print(evaluation.to_markdown({label: report}))
    print()
    print("錯的題目：")
    show_misses(results)
    print()
    print("結果存在 " + out)
    if unchecked:
        print("⚠️ 留出集還有 %d 題沒有人工抽查過（checked=false）。報告裡要寫清楚：答案由 AI 產生、人工抽查。" % unchecked)


if __name__ == "__main__":
    main()
