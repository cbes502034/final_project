"""用固定測試集評測模型，另存新報告，保留原始評測紀錄。"""
import argparse
import json
import time
from pathlib import Path
from common import ROOT, read_jsonl, strict_json, metrics
from inference import ExpenseModel, validate_expenses

def evaluate(engine, rows, checkpoint=None):
    predictions = []
    started = time.monotonic()
    for i, row in enumerate(rows, 1):
        raw = engine.generate(row["text"])
        parsed = validated = error = None
        json_valid = False
        try:
            parsed = strict_json(raw)
            json_valid = True
            validated = validate_expenses(parsed, row["text"])
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        predictions.append({"text": row["text"], "expected": row["expected"], "raw": raw,
            "parsed": parsed, "validated": validated, "error": error, "json_valid": json_valid})
        print(json.dumps({"evaluated": i, "total": len(rows), "raw_exact": parsed == row["expected"], "validated_exact": validated == row["expected"]}), flush=True)
        if checkpoint and (i == 1 or i % 5 == 0):
            checkpoint.write_text(json.dumps({"status": "running", "predictions": predictions}, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"metrics": metrics(predictions, time.monotonic() - started), "predictions": predictions}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--split", choices=["validation", "test"], default="test")
    p.add_argument("--limit", type=int)
    p.add_argument("--threads", type=int, default=4)
    p.add_argument("--adapter", default=str(ROOT / "model_training/artifacts/expense-lora"))
    p.add_argument("--base-only", action="store_true")
    p.add_argument("--output", required=True)
    args = p.parse_args()
    if args.limit is not None and args.limit < 1:
        p.error("limit must be positive")
    out = Path(args.output)
    if out.exists():
        p.error("report already exists; choose a new --output")
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = read_jsonl(ROOT / f"model_training/data/{args.split}.jsonl")
    if args.limit:
        rows = rows[:args.limit]
    result = evaluate(ExpenseModel(None if args.base_only else args.adapter, threads=args.threads), rows, out)
    result.update({"status": "complete", "split": args.split, "limited": args.limit is not None, "model": "base" if args.base_only else args.adapter})
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["metrics"], ensure_ascii=False))

if __name__ == "__main__":
    main()
