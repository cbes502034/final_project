"""
整個測試共用的設定。

領域：認證（共用元件）

⚠️ 為什麼每一支測試都先把模型服務的設定清空：
   settings 會讀 backend/.env。有人在 .env 填了真的 MODEL_API_KEY，跑 pytest 就會真的去打 Claude／OpenAI——
   花錢、變慢，而且結果每次不一樣。所以一律先清空，要測模型的測試自己用 monkeypatch 設回去。
"""

import os

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost/test")
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production-at-least-32-bytes-long")

import pytest  # noqa: E402

from app.toolkit.config import settings  # noqa: E402

_BLANK = {
    "model_provider": "openai",
    "model_base_url": "",
    "model_api_key": "",
    "model_name": "qwen2.5-1.5b-fambudget",
    "advice_provider": "",
    "advice_base_url": "",
    "advice_api_key": "",
    "advice_model_name": "",
    "model_effort": "low",
    "advice_effort": "medium",
    "model_max_tokens": 0,
}


@pytest.fixture(autouse=True)
def _no_real_model(monkeypatch):
    for name, value in _BLANK.items():
        monkeypatch.setattr(settings, name, value)
