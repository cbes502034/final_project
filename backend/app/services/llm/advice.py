"""
財務建議：把 analytics 算好的數字寫成人話。**模型不做任何算術。**

領域：數字

順序不能顛倒：
  1. services/analytics.py 從資料庫算好所有數字（收入、支出、分類、預算、存款目標）
  2. 把「算好的數字」放進 prompt，要求模型只做敘述與歸納
  3. 驗證：每一則要有 level／title／body／basis／suggest；basis 裡的數字必須來自第 1 步
  4. 存進 advices（basis_json 存數字，給使用者驗算）

使用者的理財習慣要用 toolkit/profile.py 的 to_prompt_block() 放進去（標示成資料，不是指令）。
邊界規則在 frontend/js/data.js 的 adviceRules：不給投資、保險、稅務建議，不做價值判斷。
模型沒設定時丟 client.ModelError，路由回 503——前端會用同一批數字在畫面上先寫幾則（不會存）。
"""

from __future__ import annotations

from typing import Any

from app.services.llm import client


def write_advices(numbers: dict[str, Any], finance_block: str = "") -> list[dict[str, Any]]:
    '''numbers 是 analytics 算好的數字。回傳 [{level, title, body, basis, suggest, conf}]。'''
    import json

    from app import catalog

    if not client.is_configured():
        raise client.ModelError("模型服務還沒接上")

    # a. 組 prompt：格式、邊界規則、算好的數字、使用者的理財背景
    system = chr(10).join([
        "你是家庭記帳的財務助理。根據使用者「已經算好的數字」寫 2 到 4 則建議，只回 JSON，不要其他文字。",
        '格式：{"advices": [{"level": "ok、info、warn 其中一個", "title": "20 字內", "body": "80 字內",',
        '"basis": ["依據：用下面給的數字寫成的算式"], "suggest": ["具體可以做的事"], "conf": 0 到 1 的數字}]}',
        "任何數字都只能照抄下面給的，不可以自己計算或編造。",
        "規則：",
    ] + ["- " + r["rule"] for r in catalog.ADVICE_RULES])
    prompt = chr(10).join([
        "【算好的數字（JSON）】",
        json.dumps(numbers, ensure_ascii=False),
        finance_block,
        "請寫建議：",
    ])

    # b. 叫模型
    data = client.complete_json(prompt, system=system, max_tokens=800, temperature=0.3)
    items = data.get("advices") if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise client.ModelError("模型回來的格式不對")

    # c. 只留物件、只留需要的欄位（每一欄的檢查在路由裡用 AdviceItem 做）
    keys = ("level", "title", "body", "basis", "suggest", "conf")
    return [{k: it[k] for k in keys if k in it} for it in items if isinstance(it, dict)]
