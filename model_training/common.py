"""訓練、推論和評測共用的設定。"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("HF_HOME", str(ROOT / "model_training" / ".cache" / "huggingface"))
sys.path.insert(0, str(ROOT / "backend"))
from app.services.llm.expense_rules import SYSTEM_PROMPT
BASE_MODEL = "Qwen/Qwen2.5-0.5B-Instruct"
REVISION = "7ae557604adf67be50417f59c2c2f167def9a775"

def model_source():
    cached = Path.home() / ".cache/huggingface/hub/models--Qwen--Qwen2.5-0.5B-Instruct/snapshots" / REVISION
    return str(cached) if (cached / "model.safetensors").exists() else BASE_MODEL

def messages(text, expected=None):
    rows = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": json.dumps({"text": text}, ensure_ascii=False)}]
    if expected is not None:
        rows.append({"role": "assistant", "content": json.dumps(expected, ensure_ascii=False, separators=(",", ":"))})
    return rows

def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]

def strict_json(text):
    def reject(value):
        raise ValueError("non-standard JSON constant: " + value)
    return json.loads(text, parse_constant=reject)

def metrics(predictions, seconds):
    total = len(predictions)
    if not total:
        raise ValueError("empty evaluation set")
    out = {"examples": total, "seconds": round(seconds, 2),
        "json_valid_rate": sum(r.get("json_valid", r["parsed"] is not None) for r in predictions) / total,
        "raw_exact_match": sum(r["parsed"] == r["expected"] for r in predictions) / total,
        "validated_exact_match": sum(r["validated"] == r["expected"] for r in predictions) / total}
    for field in ("category", "item", "amount"):
        correct = count = 0
        for row in predictions:
            wanted = row["expected"]["expenses"]
            got = row["parsed"].get("expenses", []) if isinstance(row["parsed"], dict) else []
            count += len(wanted)
            if isinstance(got, list) and len(got) == len(wanted):
                correct += sum(isinstance(b, dict) and a[field] == b.get(field) for a, b in zip(wanted, got))
        out[f"raw_{field}_accuracy"] = correct / count if count else 0
    return out
