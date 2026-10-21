"""本機模型服務，支援三欄 JSON 與現有專題的 items 格式。"""
import json
import logging
import os
import re
import threading
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from common import ROOT, strict_json
from inference import ExpenseModel, validate_expenses
from app.services.llm.expense_rules import project_category

app = FastAPI(title="專題支出模型")
engine = None
lock = threading.Lock()
log = logging.getLogger("expense-model")


def load_engine():
    """部署可指定完整模型；未指定時優先使用專案內合併模型。"""
    configured = os.environ.get("EXPENSE_MERGED_DIR", "").strip()
    merged = Path(configured).expanduser() if configured else ROOT / "model_training/artifacts/expense-merged"
    if configured or (merged / "model.safetensors").is_file():
        if not (merged / "config.json").is_file():
            raise FileNotFoundError("合併模型缺少 config.json")
        return ExpenseModel(None, merged=str(merged))
    adapter = Path(os.environ.get("EXPENSE_ADAPTER_DIR", str(ROOT / "model_training/artifacts/expense-lora")))
    return ExpenseModel(adapter)


@app.get("/healthz")
def healthz():
    return {"status": "ok", "modelLoaded": engine is not None}

class CompletionIn(BaseModel):
    model: str = "expense-qwen-0.5b-lora"
    messages: list[dict] = Field(min_length=1)
    max_tokens: int = 512
    temperature: float = 0

def to_project(data, text, system):
    rows = validate_expenses(data, text, with_spans=True)["expenses"]
    catalog = [{"id": m[0], "name": m[1], "kind": "expense"} for m in re.findall(r"^\s*(\d+)：(.+?)（支出）\s*$", system, re.M)]
    today = re.search(r"今天是\s*(\d{4}-\d{2}-\d{2})", system)
    day = today.group(1) if today else None
    if re.search(r"昨天|前天|上週|上個月|\d{4}[-/]\d|\d{1,2}/\d|\d+\s*[年月日號]", text):
        day = None
    return {"items": [{"span": r["span"], "date": day, "amount": r["amount"], "kind": "expense",
        "cat": project_category(r["category"], catalog), "merchant": "", "note": r["item"], "conf": {}} for r in rows]}

@app.post("/v1/chat/completions")
def complete(body: CompletionIn):
    user = next((m.get("content", "") for m in reversed(body.messages) if m.get("role") == "user"), "")
    if not isinstance(user, str):
        raise HTTPException(422, "請提供文字")
    try:
        data = json.loads(user)
        text = data.get("text", "") if isinstance(data, dict) else ""
    except ValueError:
        text = user.rsplit("\n輸入：", 1)[-1].rsplit("\n輸出：", 1)[0]
    if not isinstance(text, str) or not text.strip() or len(text) > 500:
        raise HTTPException(422, "支出文字需為 1～500 字")
    system = "\n".join(str(m.get("content", "")) for m in body.messages if m.get("role") == "system")
    if not re.search("支出|記帳", system):
        raise HTTPException(422, "此模型僅提供支出解析")
    global engine
    try:
        with lock:
            if engine is None:
                engine = load_engine()
            raw = engine.generate(text)
    except (OSError, ValueError, RuntimeError):
        log.exception("支出模型載入或生成失敗")
        raise HTTPException(503, "模型暫時無法使用，請確認模型資料夾與執行記憶體") from None
    if "每一筆要有 span" in system:
        try:
            raw = json.dumps(to_project(strict_json(raw), text, system), ensure_ascii=False)
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(503, str(exc)) from None
    return {"model": "expense-qwen-0.5b-lora", "choices": [{"message": {"role": "assistant", "content": raw}}]}
