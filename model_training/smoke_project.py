"""實際權重與模型 HTTP 契約測試；不啟動專題登入、不寫帳務資料。"""
import json
from fastapi.testclient import TestClient
from common import ROOT
from inference import ExpenseModel
import serve

def main():
    serve.engine = ExpenseModel(ROOT / "model_training/artifacts/expense-lora")
    api = TestClient(serve.app)
    text = "早餐50 午餐100 晚餐200 加油100 買周邊200"
    simple = api.post("/v1/chat/completions", json={"messages":[
        {"role":"system","content":"你是支出記帳助理"}, {"role":"user","content":json.dumps({"text":text},ensure_ascii=False)}]})
    assert simple.status_code == 200, simple.text
    raw = json.loads(simple.json()["choices"][0]["message"]["content"])
    validated = serve.validate_expenses(raw, text)
    expected = json.loads((ROOT / "model_training/artifacts/user-example.json").read_text(encoding="utf-8-sig"))
    assert validated == expected
    print(json.dumps({"status":"passed","result":validated,"scope":"real weights + model service; no database or login flow"},ensure_ascii=False))

if __name__ == "__main__":
    main()
