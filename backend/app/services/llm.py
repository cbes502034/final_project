"""
模型呼叫層。 ✦ 負責人：成員1（提供給大家共用）

===========================================================================
為什麼要有這一層？
===========================================================================
成員2 要呼叫模型做段落記帳，成員4 要呼叫模型產生建議。
如果兩個人各寫各的，會有三個問題：

1. 逾時、重試、錯誤處理各寫一遍，而且寫法不一樣
2. 換模型網址時要改兩個地方
3. 其中一個人忘記設逾時，那支 API 就會在模型卡住時一起卡死

所以**所有對模型的呼叫都經過這個檔案**，其他人只要呼叫這裡的函式。

===========================================================================
我們的模型不是商業 API
===========================================================================
課程要學的是操作 LLM，串一支別人的 API 沒有技術含量可言，
所以上線提供服務的是**我們自己微調的 Qwen2.5-1.5B**：

    Qwen2.5-1.5B-Instruct
        ↓ QLoRA 4-bit 微調（Colab 免費 T4）
        ↓ 轉成 GGUF q4_k_m（大約 1GB）
        ↓ llama.cpp 跑在 Hugging Face Space
    HTTP endpoint ← 這個檔案打的就是它

llama.cpp 提供的是 OpenAI 相容的介面，所以呼叫方式跟一般 chat API 很像。

===========================================================================
model_base_url 留空時會回傳假資料 —— 這是刻意的
===========================================================================
第 1 週的目標是「前後端串通」，那時模型還沒訓練完。
如果沒有模型就整支 API 掛掉，前端根本沒辦法開發。

所以設定留空時，這裡回傳一份**形狀正確的假資料**，
讓成員2 可以先把畫面串起來，等模型好了再把網址填上去，
其他程式碼一行都不用改。
"""

from typing import Any

import httpx

from app.core.config import settings


class ModelUnavailable(Exception):
    """
    模型服務叫不動時丟這個。

    路由接到之後要轉成 503（服務暫時無法使用）回給前端，
    **不要回 500**。500 的意思是「我們的程式壞了」，
    503 的意思是「我們沒壞，但依賴的服務現在不行」——
    前端看到 503 可以提示使用者「稍後再試」，看到 500 就只能顯示系統錯誤。
    """


def _mock_batch(text: str) -> dict[str, Any]:
    """
    模型還沒好時用的假資料。形狀跟真的一模一樣。

    刻意讓第三筆缺金額，這樣前端「缺欄位標紅 + 停用送出鈕」
    的邏輯在開發階段就測得到。
    """
    return {
        "raw": text,
        "items": [
            {
                "seq": 1,
                "span": text[:10],
                "date": "2026-09-10",
                "amount": 55,
                "kind": "expense",
                "cat": "C01",
                "merchant": "",
                "conf": {"date": 0.93, "amount": 0.99, "kind": 0.97, "cat": 0.88},
                "missing": [],
                "hint": "",
            }
        ],
        "note": "目前是假資料（MODEL_BASE_URL 未設定），形狀與真實回傳一致",
        "mock": True,
    }


async def parse_batch(text: str, categories: list[dict[str, Any]]) -> dict[str, Any]:
    """
    把一段話切成 N 筆並抽出欄位。這是整個系統的核心呼叫。

    `categories` 要把這個家庭的分類清單傳進來，寫進 prompt，
    否則模型會自己編一個分類名稱回來，那個名稱在資料庫裡不存在。

    回傳的形狀見 routers/nlp.py 的說明。

    TODO(成員2): prompt 的設計是你的主要工作，包含
                 1. few-shot 範例要放幾個、放哪些（挑最容易錯的案例）
                 2. 怎麼要求模型輸出嚴格的 JSON
                 3. 切分的指示怎麼寫（這比抽欄位更難）
    TODO(成員1): 補上重試機制 —— 模型回傳的 JSON 驗不過時，
                 帶著錯誤訊息重試一次，再失敗才丟 ModelUnavailable
    """
    if not settings.model_base_url:
        return _mock_batch(text)

    # TODO(成員1): 實際呼叫。大致長這樣：
    #     async with httpx.AsyncClient(timeout=settings.model_timeout_seconds) as client:
    #         resp = await client.post(
    #             f"{settings.model_base_url}/v1/chat/completions",
    #             json={"model": "fambudget-1.5b", "messages": [...], "temperature": 0.1},
    #         )
    #         resp.raise_for_status()
    #         return _validate(resp.json())
    #
    # temperature 要設很低（0 ~ 0.2）。這是抽取任務不是創作任務，
    # 我們要的是「每次都給一樣的答案」，不是有創意的答案。
    raise ModelUnavailable("TODO：成員1 尚未接上真實模型服務")


async def generate_advice(basis: dict[str, Any]) -> dict[str, Any]:
    """
    產生財務建議。

    ⚠️ `basis` 必須是 **analytics 已經算好的數字**，不是原始交易資料。
    模型的工作只是把數字組織成人看得懂的敘述，它不做任何算術。

    TODO(成員4): prompt 設計，把邊界規則寫成硬約束
    """
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
    raise ModelUnavailable("TODO：成員4 尚未接上真實模型服務")
