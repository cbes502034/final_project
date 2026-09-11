"""
段落記帳的 prompt。 ✦ 負責人：成員2（記帳）　✦ 分支：m2-ledger

===========================================================================
這個檔案是成員2 的主戰場
===========================================================================
整個專題最難、也最有價值的部分就在這裡。不是寫程式難，是**prompt 難**：

    切分   一段話裡到底有幾筆？切錯比抽錯更難發現
    抽欄位 日期、金額、收支方向、分類、店家
    信心度 每一欄各自給，不是整筆給一個分數

怎麼開始：先用 `_mock_batch()` 的形狀把前後端串起來，
再慢慢把 prompt 調到真的能用。**不要等 prompt 完美才接前端。**
"""

from typing import Any

from app.services.llm.client import ModelUnavailable, call_model


def _mock_batch(text: str) -> dict[str, Any]:
    """
    模型還沒好時用的假資料。形狀跟真的一模一樣。

    刻意讓某些欄位缺，這樣前端「缺欄位標紅 + 停用送出鈕」
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
    把一段話切成 N 筆並抽出欄位。

    `categories` 一定要傳，而且要傳**這個家庭實際有的分類**。
    不傳的話模型會自己編一個分類名稱回來，那個名稱在資料庫裡不存在。
    分類清單從成員3 的 GET /api/categories 來。

    TODO(成員2): 1. 組 system prompt：任務說明 + 分類清單 + 輸出格式
                 2. 放 few-shot 範例。挑最容易錯的：
                    「在全家買飲料」（店名不是家人）、
                    「媽媽給我兩千」（是收入不是支出）、
                    「三個平台訂閱共3400」（合計語意）
                 3. 呼叫 client.call_model()
                 4. 用 schemas/nlp.py 的模型驗證回傳
    """
    from app.core.config import settings

    if not settings.model_base_url:
        return _mock_batch(text)
    raise ModelUnavailable("TODO：成員2 尚未實作段落解析的 prompt")


async def parse_one(text: str, categories: list[dict[str, Any]]) -> dict[str, Any]:
    """
    單句解析。跟 parse_batch 共用同一套欄位抽取，差別只在不用切分。

    TODO(成員2): 實作。可以直接呼叫 parse_batch 再取第一筆，
                 但要注意「一句話裡其實有兩筆」的情況要怎麼處理
    """
    raise ModelUnavailable("TODO：成員2 尚未實作單句解析")
