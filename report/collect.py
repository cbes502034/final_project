"""
把簡報要用的數字從程式與結果檔收集到 report/data/facts.json。build_deck.js 只讀這個檔，數字不手打。

    python report/collect.py            # 會跑一次 pytest --collect-only 數測試
    node report/build_deck.js           # 再產生簡報

模型評測跑完（backend/eval/results/ 多了一個 JSON）、端到端測試重跑之後，重跑這兩行，簡報上的數字就跟著更新。
"""

from __future__ import annotations

import glob
import io
import json
import os
import re
import subprocess
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(ROOT, "backend")
sys.path.insert(0, BACKEND)
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("JWT_SECRET", "collect-only-not-a-real-secret-0123456789")

from app import ownership  # noqa: E402
from app.toolkit import db  # noqa: E402
import app.models  # noqa: E402,F401

DOMAIN = {"m1": "認證", "m2": "記帳", "m3": "數字", "m4": "家庭"}
#: 留出集 tags 的中文名稱
TAGS = {"single": "單筆", "multi": "一段多筆", "zh-num": "中文數字", "rel-date": "相對日期", "weekday": "星期幾",
        "abs-date": "絕對日期", "income": "收入", "no-amount": "沒講金額", "merchant": "店名陷阱", "hard": "難題",
        "no-punct": "沒有標點"}


def load_jsonl(path):
    with io.open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def main() -> int:
    facts: dict = {}

    prog = ownership.progress()
    facts["routes"] = {DOMAIN.get(k, k): len(v["done"]) + len(v["todo"]) for k, v in prog.items()}
    facts["routes_total"] = sum(facts["routes"].values())
    facts["tables"] = len(db.Base.metadata.tables)

    out = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"],
                         cwd=BACKEND, capture_output=True, text=True, encoding="utf-8",
                         env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    m = re.search(r"(\d+) tests? collected", out.stdout)
    facts["tests"] = int(m.group(1)) if m else None

    heldout = load_jsonl(os.path.join(BACKEND, "eval", "heldout.jsonl"))
    facts["heldout"] = {
        "cases": len(heldout),
        "items": sum(len(r["items"]) for r in heldout),
        "checked": sum(1 for r in heldout if r.get("checked")),
        "tags": {TAGS.get(t, t): n for t, n in Counter(t for r in heldout for t in r["tags"]).most_common()},
    }
    train = load_jsonl(os.path.join(ROOT, "ml", "data", "train.jsonl"))
    facts["train"] = {"cases": len(train), "multi": sum(1 for r in train if len(r["items"]) > 1)}

    results = {}
    for path in sorted(glob.glob(os.path.join(BACKEND, "eval", "results", "*.json"))):
        with io.open(path, encoding="utf-8") as f:
            data = json.load(f)
        misses = []
        for c in data["cases"]:
            if c.get("error") or len(misses) >= 40:
                continue
            wrong = []
            pairs = list(zip(c["pred"], c["gold"])) if len(c["pred"]) == len(c["gold"]) else []
            if not pairs:
                misses.append({"text": c["text"], "what": "切成 %d 筆（答案 %d 筆）" % (len(c["pred"]), len(c["gold"]))})
                continue
            for p, g in pairs:
                for f_ in ("date", "amount", "kind", "cat"):
                    if (p.get(f_) or None) != (g.get(f_) or None) and not (
                            f_ == "amount" and p.get(f_) is not None and g.get(f_) is not None
                            and abs(float(p[f_]) - float(g[f_])) < 0.01):
                        wrong.append("%s：%s → 應為 %s" % ({"date": "日期", "amount": "金額", "kind": "收支",
                                                           "cat": "分類"}[f_], p.get(f_), g.get(f_)))
            if wrong:
                misses.append({"text": c["text"], "what": "；".join(wrong[:2])})
        results[data["label"]] = {"model": data["model"], "when": data["when"], "report": data["report"],
                                  "misses": misses}
    facts["eval"] = results

    e2e_path = os.path.join(ROOT, "report", "data", "e2e.json")
    if os.path.exists(e2e_path):
        with io.open(e2e_path, encoding="utf-8") as f:
            e2e = json.load(f)
        by = {}
        for s in e2e["steps"]:
            d = by.setdefault(s["domain"], [0, 0])
            d[0] += s["ok"]
            d[1] += 1
        facts["e2e"] = {"passed": e2e["passed"], "total": e2e["total"], "when": e2e["when"],
                        "by_domain": {k: {"passed": v[0], "total": v[1]} for k, v in by.items()},
                        "model_steps": [s for s in e2e["steps"] if s["path"] in ("/api/nlp/parse-batch",
                                                                                 "/api/advices/generate")]}

    os.makedirs(os.path.join(ROOT, "report", "data"), exist_ok=True)
    with io.open(os.path.join(ROOT, "report", "data", "facts.json"), "w", encoding="utf-8") as f:
        json.dump(facts, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in facts.items() if k not in ("eval",)}, ensure_ascii=False)[:600])
    print("eval:", list(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
