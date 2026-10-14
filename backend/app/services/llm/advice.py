"""
財務建議：把 analytics 算好的數字寫成人話。**模型不做任何算術。**

領域：數字

順序不能顛倒：
  1. services/analytics.py 從資料庫算好所有數字（收入、支出、分類、預算、存款目標）
  2. build_prompt()：把「算好的數字」連同常用的比例（derive() 先算好）放進 prompt，要求模型只做敘述與歸納
  3. 叫模型：complete_json(..., purpose="advice", schema=ADVICE_SCHEMA)——用 ADVICE_* 那組設定，
     格式由結構化輸出保證
  4. 檢查數字：title／body／basis 裡出現的每一個數字，都要找得到出處（grounded()）；
     找不到的那一則信心度壓到 0.3，前端會標出來——模型自己算出來的數字，使用者不該照單全收
  5. 路由用 AdviceItem 驗證格式、存進 advices（basis_json 存數字，給使用者驗算）

使用者的理財習慣要用 toolkit/profile.py 的 to_prompt_block() 放進去（標示成資料，不是指令）。
邊界規則在 catalog.ADVICE_RULES（正本是 frontend/js/data.js 的 adviceRules）：不給投資、保險、稅務建議，不做價值判斷。
模型沒設定時丟 client.ModelError，路由回 503——前端會用同一批數字在畫面上先寫幾則（不會存）。
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.services.llm import client

#: 模型要交的格式。每一欄都 required：結構化輸出（Claude 的 output_config.format、OpenAI 的 response_format）
#: 要求所有欄位都列在 required、而且 additionalProperties 是 false
ADVICE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["advices"],
    "properties": {
        "advices": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["level", "title", "body", "basis", "suggest", "conf"],
                "properties": {
                    "level": {"type": "string", "enum": ["ok", "info", "warn"]},
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                    "basis": {"type": "array", "items": {"type": "string"}},
                    "suggest": {"type": "array", "items": {"type": "string"}},
                    "conf": {"type": "number"},
                },
            },
        }
    },
}

#: 數字對不上出處時，這一則的信心度最多剩這麼多
UNGROUNDED_CONF = 0.3

_NUMBER = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(萬|%|％)?")


def derive(numbers: dict[str, Any]) -> dict[str, Any]:
    """模型最常「順手」算的幾個比例，先在這裡算好交給它，它就不用自己算。全部是百分比，四捨五入到小數一位。"""
    def num(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0

    income, expense = num(numbers.get("income")), num(numbers.get("expense"))
    out: dict[str, Any] = {}
    if income > 0:
        out["支出佔收入（%）"] = round(expense / income * 100, 1)
    savings = numbers.get("savings") or {}
    if isinstance(savings, dict) and savings.get("ratio") is not None:
        out["已用掉可支配上限（%）"] = round(num(savings.get("ratio")) * 100, 1)
    if expense > 0:
        out["各分類佔支出（%）"] = {
            str(c.get("name") or ""): round(num(c.get("amount")) / expense * 100, 1)
            for c in numbers.get("byCat") or [] if isinstance(c, dict)
        }
    return out


def build_prompt(numbers: dict[str, Any], finance_block: str = "") -> tuple[str, str]:
    """(system, prompt)。prompt 裡只有「算好的數字」與「換算好的比例」，模型照抄就好。"""
    from app import catalog

    system = "\n".join([
        "你是家庭記帳的財務助理。根據使用者「已經算好的數字」寫 2 到 4 則建議。",
        "每一則：level 是 ok（做得好）、info（提醒）、warn（要注意）其中一個；title 20 字內；body 80 字內；",
        "basis 是依據，每一條都用下面給的數字寫成算式或句子；suggest 是具體可以做的事；conf 是 0 到 1 的信心度。",
        "任何數字都只能照抄下面給的（包含換算好的比例），不可以自己計算、四捨五入成別的數或編造。",
        "沒有記帳資料（支出與收入都是 0）時，只寫一則 info 提醒先記帳。",
        "規則：",
    ] + ["- " + r["rule"] for r in catalog.ADVICE_RULES])
    prompt = "\n".join([
        "【算好的數字（JSON）】",
        json.dumps(numbers, ensure_ascii=False),
        "【換算好的比例（JSON）】",
        json.dumps(derive(numbers), ensure_ascii=False),
        finance_block,
        "請寫建議。",
    ])
    return system, prompt


def allowed_numbers(numbers: dict[str, Any]) -> set[float]:
    """建議裡可以出現的數字：算好的數字、換算好的比例、日期裡的年月，再加 0～12（月份、筆數、幾個月）。"""
    found: set[float] = set(float(n) for n in range(13))

    def walk(v):
        if isinstance(v, bool) or v is None:
            return
        if isinstance(v, (int, float)):
            found.add(round(float(v), 2))
            if 0 < abs(v) <= 1:                       # 0.86 這種比例，寫成 86% 也算有出處
                found.add(round(float(v) * 100, 1))
                found.add(float(round(float(v) * 100)))
        elif isinstance(v, str):
            for m in _NUMBER.finditer(v):
                found.add(round(float(m.group(1).replace(",", "")), 2))
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, (list, tuple)):
            for x in v:
                walk(x)

    walk(numbers)
    walk(derive(numbers))
    return found


def grounded(item: dict[str, Any], allowed: set[float]) -> bool:
    """title、body、basis 裡的每一個數字都找得到出處？（suggest 是建議做的事，例如「每週少外食 2 次」，不檢查）"""
    texts = [str(item.get("title") or ""), str(item.get("body") or "")]
    texts += [str(b) for b in item.get("basis") or [] if b is not None]
    for text in texts:
        for m in _NUMBER.finditer(text):
            value = float(m.group(1).replace(",", ""))
            if m.group(2) == "萬":
                # 「1.4 萬」：照寫出來的位數四捨五入後對得上就算
                step = 10 ** -len(m.group(1).partition(".")[2]) * 10000
                if not any(abs(a - value * 10000) <= step / 2 for a in allowed):
                    return False
            elif round(value, 2) not in allowed:
                return False
    return True


def write_advices(numbers: dict[str, Any], finance_block: str = "") -> list[dict[str, Any]]:
    '''numbers 是 analytics 算好的數字。回傳 [{level, title, body, basis, suggest, conf}]。'''
    if not client.is_configured():
        raise client.ModelError("模型服務還沒接上")

    # a. 組 prompt：格式、邊界規則、算好的數字與比例、使用者的理財背景
    system, prompt = build_prompt(numbers, finance_block)

    # b. 叫模型（用 ADVICE_* 那組設定；格式由結構化輸出保證）
    data = client.complete_json(prompt, system=system, max_tokens=800, temperature=0.3,
                                purpose="advice", schema=ADVICE_SCHEMA)
    items = data.get("advices") if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise client.ModelError("模型回來的格式不對")

    # c. 只留物件、只留需要的欄位（每一欄的檢查在路由裡用 AdviceItem 做）；
    #    數字找不到出處的，信心度壓低，讓使用者知道這一則要自己驗算
    allowed = allowed_numbers(numbers)
    keys = ("level", "title", "body", "basis", "suggest", "conf")
    out = []
    for it in items:
        if not isinstance(it, dict):
            continue
        one = {k: it[k] for k in keys if k in it}
        if not grounded(one, allowed):
            try:
                one["conf"] = min(float(one.get("conf", 1)), UNGROUNDED_CONF)
            except (TypeError, ValueError):
                one["conf"] = UNGROUNDED_CONF
        out.append(one)
    return out
