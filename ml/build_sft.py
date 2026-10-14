"""
訓練資料 → 微調用的對話格式：ml/data/sft.jsonl、ml/data/tools.json。

領域：記帳（微調是加分項）

    python ml/make_data.py       # 先產生 ml/data/train.jsonl
    python ml/build_sft.py       # 再轉成對話格式

每一行是一段對話：
    system     parse.build_prompt() 組的規則＋今天＋分類清單      ← 跟上線時一字不差
    user       parse.build_prompt() 組的範例＋輸入
    assistant  一個 record_transactions 工具呼叫，參數就是正確答案

⚠️ 為什麼要「跟上線時一字不差」：微調學到的是「看到這種 prompt 就這樣回」。
   上線時 prompt 差一個字，模型就像沒看過一樣。所以這裡直接 import 後端的 build_prompt，不自己抄一份。
⚠️ 工具定義（tools.json）在 Colab 裡交給 tokenizer.apply_chat_template(..., tools=...)，
   Qwen 會把它排進 system；上線時 llama-server --jinja 用的是同一個模板，兩邊才對得上。
"""

from __future__ import annotations

import io
import json
import os
import random
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("JWT_SECRET", "ml-only-not-a-real-secret-at-least-32-bytes")

from app.services.llm import parse  # noqa: E402
from app.toolkit import dates  # noqa: E402

DATA = os.path.join(ROOT, "ml", "data")

#: 跟 client._call_openai 送出去的 tools 一模一樣
TOOL = {"type": "function", "function": {"name": parse.RECORD_TOOL["name"],
                                         "description": parse.RECORD_TOOL["description"],
                                         "parameters": parse.RECORD_TOOL["input_schema"]}}


def answer(ex: dict) -> dict:
    """正確答案 → 模型要交的工具參數（分類換成這一題清單裡的 id、每一欄給一個信心度）。"""
    ids = {c["name"]: c["id"] for c in ex["categories"]}
    items = []
    for g in ex["items"]:
        span = g["span"]
        amount = g["amount"]
        arabic = bool(re.search(r"\d", re.sub(r"7-11|\d+月\d+[日號]|\d+/\d+|\d+號", "", span)))
        items.append({
            "span": span,
            "date": g["date"],
            "amount": amount,
            "kind": g["kind"],
            "cat": ids[g["cat"]],
            "merchant": g.get("merchant", ""),
            "note": g.get("note", ""),
            "conf": {"date": 0.95 if dates.find(span, ex["today"]) else 0.9,
                     "amount": 0 if amount is None else (0.98 if arabic else 0.9),
                     "kind": 0.97, "cat": 0.9},
        })
    return {"items": items}


def to_chat(ex: dict) -> dict:
    system, prompt = parse.build_prompt(ex["text"], ex["categories"], ex["today"])
    return {"id": ex["id"], "messages": [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": TOOL["function"]["name"], "arguments": answer(ex)}}]},
    ]}


def main() -> None:
    src = os.path.join(DATA, "train.jsonl")
    if not os.path.exists(src):
        sys.exit("先跑 python ml/make_data.py")
    with io.open(src, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    random.Random(7).shuffle(rows)
    n_val = max(1, len(rows) // 20)                          # 5% 當驗證集，看有沒有過擬合
    with io.open(os.path.join(DATA, "sft.jsonl"), "w", encoding="utf-8", newline="\n") as f:
        for i, ex in enumerate(rows):
            row = to_chat(ex)
            row["split"] = "val" if i < n_val else "train"
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    with io.open(os.path.join(DATA, "tools.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump([TOOL], f, ensure_ascii=False, indent=1)
    print("寫了 %d 段對話（驗證集 %d）到 ml/data/sft.jsonl；工具定義在 ml/data/tools.json" % (len(rows), n_val))


if __name__ == "__main__":
    main()
