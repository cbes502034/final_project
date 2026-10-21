"""三欄支出解析與原文證據驗證；不寫資料庫。負責人：成員2（記帳）。"""
import json
import re
from app.services.llm import client
from app.services.llm.expense_rules import CATEGORIES, SYSTEM_PROMPT, fixed_category, grounded_amount

def validate_expenses(data, text, *, with_spans=False):
    if not isinstance(data, dict) or set(data) != {"expenses"} or not isinstance(data["expenses"], list):
        raise client.ModelError("模型回來的支出格式不對")
    rows, positions = [], []
    cursor = 0
    for raw in data["expenses"]:
        if not isinstance(raw, dict) or set(raw) != {"category", "item", "amount"}:
            raise client.ModelError("每筆支出必須只有 category、item、amount")
        item = raw["item"]
        if not isinstance(item, str) or not item.strip():
            raise client.ModelError("模型沒有回有效品項")
        category, item = fixed_category(item.strip())
        peripheral_at, literal_at = text.find("周邊", cursor), text.find(item, cursor)
        peripheral = item == "娛樂" and peripheral_at >= 0 and (literal_at < 0 or peripheral_at < literal_at)
        if peripheral:
            category = "其他"
        category = category or raw["category"]
        if category not in CATEGORIES:
            raise client.ModelError("模型回了不合法的支出分類")
        anchor = "周邊" if peripheral else item
        at = text.find(anchor, cursor)
        if at < 0:
            raise client.ModelError("模型品項對不到原文，請重新解析或手動輸入")
        before = re.search(r"(?:付了?|花了?)[\d,\.零〇一二兩三四五六七八九十百千萬億點]+\s*(?:元|塊)\s*(?:購?買了?)+\s*$", text[cursor:at])
        positions.append(cursor + before.start() if before else at)
        cursor = at + len(anchor)
        rows.append({"category": category, "item": item, "amount": raw["amount"]})
    for i, row in enumerate(rows):
        end = positions[i + 1] if i + 1 < len(rows) else len(text)
        span = text[positions[i]:end]
        row["amount"] = grounded_amount(row["amount"], span, item=row["item"])
        if with_spans:
            row["span"] = span.strip(" ，；。\n")
    return {"expenses": rows}

def parse_expenses(text):
    text = text.strip()
    if not text or len(text) > 500:
        raise ValueError("請輸入 1～500 字的支出內容")
    if re.search(r"美元|美金|日圓|日元|港幣|人民幣|歐元|英鎊|澳幣|加幣|韓元|韓圓|泰銖|新加坡幣|\b(?:USD|JPY|HKD|CNY|RMB|EUR|GBP|AUD|CAD|KRW|THB|SGD)\b|US\$|[€£¥]", text, re.I):
        raise ValueError("此三欄支出格式目前只接受新臺幣")
    if not client.is_configured():
        raise client.ModelError("模型服務還沒接上，請先設定 MODEL_BASE_URL")
    data = client.complete_json(json.dumps({"text": text}, ensure_ascii=False), system=SYSTEM_PROMPT, temperature=0, max_tokens=2048)
    return validate_expenses(data, text)
