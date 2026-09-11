"""
財務建議的 prompt。 ✦ 負責人：成員3（數字與建議）　✦ 分支：m3-analytics

===========================================================================
這個檔案唯一要記住的一條規則：模型不做算術
===========================================================================
傳進來的 `basis` 必須是 **analytics.build_basis() 已經算好的數字**，
不是原始交易資料。模型的工作只是把數字組織成人看得懂的敘述，
**它連算錯的機會都沒有**。

財務數字算錯會讓使用者做出錯誤決定，而語言模型本來就不擅長算術。
"""

from typing import Any

from app.services.llm.client import ModelUnavailable, call_model

# 寫進 prompt 的硬約束。這幾條要原文放進 system prompt，不要改寫。
BOUNDARY_RULES = [
    "只根據提供的數字敘述，不要自己計算或推估任何金額",
    "每一條建議都要指出它根據哪幾個數字",
    "不提供投資、保險、稅務建議 —— 那些是受規範的專業意見",
    "不對個人做價值判斷，只描述數字與趨勢，不要說「你太浪費」",
]


async def generate(basis: dict[str, Any]) -> dict[str, Any]:
    """
    產生財務建議。

    TODO(成員3): 1. 把 BOUNDARY_RULES 放進 system prompt
                 2. 把 basis 的數字整理成好讀的格式放進 user prompt
                 3. 要求輸出 title / body / level 三個欄位
                 4. 用 schemas/advice.py 驗證回傳
    """
    from app.core.config import settings

    if not settings.model_base_url:
        return {
            "advices": [
                {
                    "title": "（示範）餐飲支出佔比偏高",
                    "body": "目前是假資料，MODEL_BASE_URL 設定後會換成真實產出。",
                    "level": "info",
                }
            ],
            "mock": True,
        }
    raise ModelUnavailable("TODO：成員3 尚未實作建議生成的 prompt")
