"""
自然語言記帳：一句話 → 一筆、一段話 → 好幾筆。**只解析，不寫入。**

負責人：成員2（記帳）　✦ 分支：m2-ledger

要做的事（成員2 的 LLM 工作）：
  1. 組 prompt：分類清單（GET /api/categories 那一份）、今天日期（「昨天」要換算）、few-shot 範例
  2. 呼叫 services/llm/client.complete_json()
  3. 驗證：金額 > 0、日期 YYYY-MM-DD、cat 在清單裡；缺的欄位放進 missing、信心度放進 conf
  4. 模型沒設定（client 回 None）或叫不動（ModelError）→ 路由回 503，前端會用規則頂著

回傳形狀跟前端的 mock 一樣（docs/02-前後端串接契約.md 的 POST /api/nlp/parse-batch）：
    {"raw": 原文, "items": [{"seq", "span", "date", "amount", "kind", "cat", "merchant", "note",
                            "conf": {"date", "amount", "kind", "cat"}, "missing": [...], "hint": ""}], "note": ""}

⚠️ 切分比抽欄位難，而且切錯比抽錯更難發現——每一筆都要帶 span（對應原句的哪一段）。
"""

from __future__ import annotations

from typing import Any

from app.services.llm import client

MODEL_UNAVAILABLE = "模型服務還沒接上，先用前端的規則解析"


def parse_batch(text: str, categories: list[dict[str, Any]], today: str) -> dict[str, Any]:
    '''一段話 → 好幾筆。模型沒設定丟 client.ModelError（路由轉 503）。'''
    import json
    from datetime import date

    from app.toolkit import money

    if not client.is_configured():
        raise client.ModelError(MODEL_UNAVAILABLE)

    # a. 組 prompt：規則、今天日期、分類清單（模型只能從這裡挑）、一組範例
    rules = [
        "你是記帳助理，把使用者的一段話切成一筆一筆的收支，只回 JSON，不要任何說明文字。",
        "每一筆要有 span（原句裡對應的那一段）、date（YYYY-MM-DD）、amount（正數）、",
        "kind（expense 或 income）、cat（下面分類清單裡的 id）、merchant（店家，沒有就空字串）、",
        "note（備註，沒有就空字串）、conf（date、amount、kind、cat 各一個 0 到 1 的信心度）。",
        "抽不到的欄位填 null，不要猜。「昨天」「前天」要換算成日期。",
        "今天是 " + today + "。分類清單：",
    ]
    for c in categories:
        rules.append("  %s：%s（%s）" % (c["id"], c["name"], "收入" if c["kind"] == "income" else "支出"))
    ids = {c["name"]: c["id"] for c in categories}
    example = {"items": [
        {"span": "早上買早餐55", "date": today, "amount": 55, "kind": "expense", "cat": ids.get("餐飲", ""),
         "merchant": "", "note": "早餐", "conf": {"date": 0.9, "amount": 0.99, "kind": 0.97, "cat": 0.9}},
        {"span": "晚上加油", "date": today, "amount": None, "kind": "expense", "cat": ids.get("交通", ""),
         "merchant": "", "note": "加油", "conf": {"date": 0.9, "amount": 0, "kind": 0.95, "cat": 0.85}},
    ]}
    prompt = chr(10).join([
        "範例輸入：早上買早餐55，晚上加油",
        "範例輸出：" + json.dumps(example, ensure_ascii=False),
        "輸入：" + text,
        "輸出：",
    ])

    # b. 叫模型（逾時、重試、剝掉 JSON 外面的包裝，client 都做好了）
    data = client.complete_json(prompt, system=chr(10).join(rules), max_tokens=1024)
    raw_items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(raw_items, list):
        raise client.ModelError("模型回來的格式不對")

    # c. 一筆一筆驗證：抽不到、不合理的欄位設成 None，放進 missing
    def score(value):
        try:
            return min(1.0, max(0.0, float(value)))
        except (TypeError, ValueError):
            return 0.0

    kinds = {c["id"]: c["kind"] for c in categories}
    items = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        missing = []
        try:
            day = date.fromisoformat(str(raw.get("date"))).isoformat()
        except ValueError:
            day = None
            missing.append("date")
        try:
            amount = money.to_decimal(raw.get("amount"), allow_negative=False)
        except money.InvalidAmount:
            amount = None
        if amount is None or amount <= 0:
            amount = None
            missing.append("amount")
        kind = raw.get("kind") if raw.get("kind") in ("expense", "income") else None
        if kind is None:
            missing.append("kind")
        cat = str(raw.get("cat") or "")
        if cat not in kinds or (kind is not None and kinds[cat] != kind):
            cat = None
            missing.append("cat")
        conf = raw.get("conf") if isinstance(raw.get("conf"), dict) else {}
        items.append({
            "seq": len(items) + 1,
            "span": str(raw.get("span") or "")[:100],
            "date": day,
            "amount": float(amount) if amount is not None else None,
            "kind": kind,
            "cat": cat,
            "merchant": str(raw.get("merchant") or "")[:50],
            "note": str(raw.get("note") or "")[:100],
            "conf": {k: score(conf.get(k)) for k in ("date", "amount", "kind", "cat")},
            "missing": missing,
            "hint": "這一筆有欄位抽不到，補上才能存" if missing else "",
        })
    return {"raw": text, "items": items,
            "note": "這段話被切成 %d 筆。切分本身也是模型的判斷，請對照原句檢查。" % len(items)}


def parse_one(text: str, categories: list[dict[str, Any]], today: str) -> dict[str, Any]:
    '''一句話 → 一筆。跟 parse_batch 用同一套 prompt，拿第一筆。'''
    result = parse_batch(text, categories, today)
    if not result["items"]:
        raise client.ModelError("模型沒有從這句話解析出任何一筆")
    return result["items"][0]
