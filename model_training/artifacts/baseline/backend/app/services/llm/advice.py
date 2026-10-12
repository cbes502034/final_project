"""
財務建議：把 analytics 算好的數字寫成人話。**模型不做任何算術。**

負責人：成員3（數字）　✦ 分支：m3-analytics

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
    """numbers 是 analytics.summary() 的結果。回傳 [{level, title, body, basis, suggest, conf}]。"""
    if not client.is_configured():
        raise client.ModelError("模型服務還沒接上")
    raise NotImplementedError("成員3：組 prompt → client.complete_json → 驗證")  # TODO(成員3)
