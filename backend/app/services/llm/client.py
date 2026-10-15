"""
共用的模型呼叫層：逾時、重試、把回來的 JSON 交出去。**成員2 的解析、成員3 的建議都呼叫它。**

負責人：成員1（共用元件，第 1 週先做出來）

    from app.services.llm import client

    out = client.complete(prompt, system="你是記帳助理……", max_tokens=400)
    if out is None:                  # 沒設定模型服務（MODEL_BASE_URL 留空）
        ...                          # 呼叫的人自己決定：回 503，或用規則頂著
    data = client.complete_json(prompt)   # 要 JSON 的時候用這支，解析失敗丟 ModelError

模型服務是 llama.cpp 的 OpenAI 相容介面（POST {MODEL_BASE_URL}/v1/chat/completions）。
⚠️ 叫不動的時候路由要回 **503**（errors.service_unavailable），不是 500——那是外部問題，不是我們的 bug。
"""

from __future__ import annotations

import json
import time
from typing import Any

import httpx

from app.toolkit.config import settings

__all__ = ["ModelError", "is_configured", "complete", "complete_json"]


class ModelError(RuntimeError):
    """模型服務沒回應、回錯誤、或回來的不是要的格式。路由接到轉成 503。"""


def is_configured() -> bool:
    return bool(settings.model_base_url.strip())


def complete(
    prompt: str,
    *,
    system: str = "",
    max_tokens: int = 512,
    temperature: float = 0.1,
    retries: int = 1,
    client: httpx.Client | None = None,
) -> str | None:
    """送一段 prompt，回模型寫的文字。沒設定 MODEL_BASE_URL 回 None。

    retries：逾時或 5xx 再試幾次（中間等 0.5、1 秒）。4xx 不重試——那是我們送錯了。
    """
    if not is_configured():
        return None
    url = settings.model_base_url.rstrip("/") + "/v1/chat/completions"
    headers = {"content-type": "application/json"}
    if settings.model_api_key:
        headers["authorization"] = "Bearer " + settings.model_api_key
    messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
    body = {"model": settings.model_name, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}

    own = client is None
    client = client or httpx.Client(timeout=settings.model_timeout_seconds)
    try:
        for attempt in range(retries + 1):
            try:
                res = client.post(url, json=body, headers=headers)
            except httpx.HTTPError as exc:
                if attempt < retries:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                raise ModelError("模型服務沒有回應：%s" % exc.__class__.__name__) from None
            if res.status_code >= 500 and attempt < retries:
                time.sleep(0.5 * (attempt + 1))
                continue
            if res.status_code != 200:
                raise ModelError("模型服務回 %d" % res.status_code)
            try:
                return res.json()["choices"][0]["message"]["content"]
            except (ValueError, KeyError, IndexError):
                raise ModelError("模型服務回來的格式看不懂") from None
    finally:
        if own:
            client.close()
    return None


def complete_json(prompt: str, **kwargs: Any) -> Any:
    """跟 complete 一樣，但要求回 JSON 並解析。模型常在 JSON 外面包 ```json，這裡會剝掉。"""
    text = complete(prompt, **kwargs)
    if text is None:
        return None
    raw = text.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw[raw.find("\n") + 1:] if "\n" in raw else raw
    start = min([i for i in (raw.find("{"), raw.find("[")) if i >= 0], default=-1)
    if start < 0:
        raise ModelError("模型沒有回 JSON")
    try:
        return json.loads(raw[start:])
    except json.JSONDecodeError:
        end = max(raw.rfind("}"), raw.rfind("]"))
        try:
            return json.loads(raw[start:end + 1])
        except json.JSONDecodeError:
            raise ModelError("模型回的 JSON 壞掉了") from None
