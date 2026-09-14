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
    """一段話 → 好幾筆。模型沒設定丟 client.ModelError（路由轉 503）。"""
    if not client.is_configured():
        raise client.ModelError(MODEL_UNAVAILABLE)
    raise NotImplementedError("成員2：組 prompt → client.complete_json → 驗證欄位")  # TODO(成員2)


def parse_one(text: str, categories: list[dict[str, Any]], today: str) -> dict[str, Any]:
    """一句話 → 一筆。可以直接拿 parse_batch 的第一筆。"""
    if not client.is_configured():
        raise client.ModelError(MODEL_UNAVAILABLE)
    raise NotImplementedError("成員2：跟 parse_batch 共用同一套 prompt")  # TODO(成員2)
