"""恢復後的資料、提示詞、訓練遮罩與解析回歸測試。"""
import hashlib
import json
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from common import ROOT, SYSTEM_PROMPT, read_jsonl, strict_json
from inference import validate_expenses
from train import encode
from revalidate_reports import revalidate
import serve

def test_dataset_exactly_matches_original_training():
    report = json.loads((ROOT / "model_training/artifacts/expense-lora/training_report.json").read_text())
    assert hashlib.sha256((ROOT / "model_training/data/train.jsonl").read_bytes()).hexdigest() == report["training_data_sha256"]
    splits = {s: read_jsonl(ROOT / f"model_training/data/{s}.jsonl") for s in ("train", "validation", "test")}
    assert [len(splits[s]) for s in splits] == [150, 90, 91]
    for a, b in (("train", "validation"), ("train", "test"), ("validation", "test")):
        assert not ({r["text"] for r in splits[a]} & {r["text"] for r in splits[b]})

def test_prompt_exactly_matches_original_cache():
    old = json.loads((ROOT / "model_training/recovery_manifest.json").read_text(encoding="utf-8"))
    assert hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest() == old["original_prompt_sha256"]

def test_stored_evaluation_is_reproduced_without_generation():
    for name in ("base-test", "lora-test"):
        report = json.loads((ROOT / f"model_training/artifacts/{name}.json").read_text(encoding="utf-8"))
        expected = report["metrics"]
        restored = revalidate(report)["metrics"]
        for key in expected:
            assert restored[key] == expected[key]

def test_labels_only_train_assistant():
    class Tokenizer:
        def apply_chat_template(self, messages, **kw):
            return [1, 2, 3] if kw.get("add_generation_prompt") else [1, 2, 3, 4, 5]
    assert encode(Tokenizer(), {"text": "早餐50", "expected": {}}, 10)[1] == [-100, -100, -100, 4, 5]
    with pytest.raises(ValueError):
        encode(Tokenizer(), {"text": "早餐50", "expected": {}}, 4)

@pytest.mark.parametrize("text,amount,expected", [("零食100",100,100), ("午餐大約100",100,None), ("早餐",50,None), ("午餐50或60",50,None)])
def test_amount_evidence(text, amount, expected):
    item = "零食" if "零食" in text else ("午餐" if "午餐" in text else "早餐")
    r = validate_expenses({"expenses": [{"category": "食", "item": item, "amount": amount}]}, text)
    assert r["expenses"][0]["amount"] == expected

def test_service_preserves_current_project_contract(monkeypatch):
    monkeypatch.setattr(serve, "engine", SimpleNamespace(generate=lambda text:'{"expenses":[{"category":"食","item":"午餐","amount":100}]}'))
    api = TestClient(serve.app)
    r = api.post("/v1/chat/completions", json={"messages": [
        {"role":"system","content":"你是記帳助理。每一筆要有 span。今天是 2026-10-14。\n  1：餐飲（支出）"},
        {"role":"user","content":"範例輸入：早餐50\n輸入：午餐100\n輸出："}]})
    assert r.status_code == 200
    data = json.loads(r.json()["choices"][0]["message"]["content"])
    assert data["items"][0]["cat"] == "1" and data["items"][0]["amount"] == 100

def test_json_rejects_nonstandard_numbers():
    with pytest.raises(ValueError):
        strict_json('{"amount":NaN}')


def test_merged_model_path_is_used(monkeypatch, tmp_path):
    (tmp_path / "config.json").write_text("{}")
    monkeypatch.setenv("EXPENSE_MERGED_DIR", str(tmp_path))
    seen = []
    sentinel = object()
    def load(adapter, *, merged):
        seen.append((adapter, merged))
        return sentinel
    monkeypatch.setattr(serve, "ExpenseModel", load)
    assert serve.load_engine() is sentinel
    assert seen == [(None, str(tmp_path))]


def test_missing_model_is_reported_as_unavailable(monkeypatch, tmp_path):
    monkeypatch.setenv("EXPENSE_MERGED_DIR", str(tmp_path / "missing"))
    monkeypatch.setattr(serve, "engine", None)
    api = TestClient(serve.app)
    assert api.get("/healthz").json()["modelLoaded"] is False
    response = api.post("/v1/chat/completions", json={"messages": [
        {"role": "system", "content": "支出解析"}, {"role": "user", "content": "午餐100"},
    ]})
    assert response.status_code == 503
    assert str(tmp_path) not in response.text
