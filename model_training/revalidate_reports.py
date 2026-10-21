"""重驗保存的原始模型輸出，另存 *.revalidated.json 保留舊紀錄。"""
import argparse
import json
import os
from pathlib import Path
from common import strict_json, metrics
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("JWT_SECRET", "report-validation-only-not-a-production-key")
from app.services.llm.expenses import validate_expenses

def revalidate(report):
    for row in report["predictions"]:
        row.update(parsed=None, validated=None, json_valid=False)
        try:
            row["parsed"] = strict_json(row["raw"])
            row["json_valid"] = True
            row["validated"] = validate_expenses(row["parsed"], row["text"])
            row["error"] = None
        except Exception as exc:
            row["error"] = f"{type(exc).__name__}: {exc}"
    report["metrics"] = metrics(report["predictions"], report.get("metrics", {}).get("seconds", 0))
    report["status"] = "complete"
    return report

def main():
    p = argparse.ArgumentParser()
    p.add_argument("reports", nargs="+")
    args = p.parse_args()
    for name in args.reports:
        path = Path(name)
        out = path.with_suffix(".revalidated.json")
        if out.exists():
            p.error("output already exists: " + str(out))
        report = revalidate(json.loads(path.read_text(encoding="utf-8")))
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"output": str(out), "metrics": report["metrics"]}, ensure_ascii=False))

if __name__ == "__main__":
    main()
