"""
共用的模型呼叫層：逾時、重試、工具呼叫、把回來的 JSON 交出去。**記帳解析、財務建議都呼叫它。**

領域：認證（共用元件）

    from app.services.llm import client

    out = client.complete(prompt, system="你是記帳助理……", max_tokens=400)
    if out is None:                  # 沒設定模型服務
        ...                          # 呼叫的人自己決定：回 503，或用規則頂著
    data = client.complete_json(prompt)                    # 要 JSON 的時候用這支，解析失敗丟 ModelError
    data = client.complete_json(prompt, tool=SOME_TOOL)    # 要模型用「工具呼叫」交出結果（function calling）
    data = client.complete_json(prompt, purpose="advice")  # 財務建議用 ADVICE_* 那一組設定

===========================================================================
兩種模型服務（MODEL_PROVIDER）
===========================================================================
openai     OpenAI 相容的 POST {MODEL_BASE_URL}/v1/chat/completions。
           OpenAI、我們微調後放在 Hugging Face Space 的 llama-server、Colab 上臨時開的服務都走這條。
anthropic  Claude，走官方的 anthropic 套件。

兩條路對呼叫的人完全一樣：同一個 complete_json(prompt, tool=…)，拿回同一個 dict。

===========================================================================
工具呼叫（function calling）
===========================================================================
tool 是一個 {"name", "description", "input_schema"}（JSON Schema）。
  · openai     送 tools ＋ tool_choice="required"，回來的 tool_calls[0].function.arguments 就是答案
  · anthropic  送 tools（strict：參數一定符合 schema），從 tool_use 區塊拿 input
  · 服務不支援工具呼叫、模型改用一般文字回 JSON 的話，一樣接得住（退回去解析文字）
  · 服務回 400 說不收某個參數（max_tokens、temperature、tools、response_format），拿掉或換掉再送一次

⚠️ 叫不動的時候路由要回 **503**（errors.service_unavailable），不是 500——那是外部問題，不是我們的 bug。
"""

from __future__ import annotations

import json
import time
from typing import Any

import httpx

from app.toolkit import config
from app.toolkit.config import settings

__all__ = ["ModelError", "is_configured", "complete", "complete_json", "model_name"]

#: MODEL_PROVIDER=anthropic 而 MODEL_NAME 不是 claude- 開頭時用這一顆（定義在 config，nlp_parses.model_ver 才記得對）
CLAUDE_DEFAULT = config.CLAUDE_DEFAULT

#: 這幾顆支援伺服器端的 refusal fallback：模型婉拒時，伺服器自動換一顆能回答的模型重跑同一個請求
_CLAUDE_FALLBACK_MODELS = ("claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5")


class ModelError(RuntimeError):
    """模型服務沒回應、回錯誤、或回來的不是要的格式。路由接到轉成 503。"""


# ===========================================================================
# 設定：記帳一組、建議一組（建議的每一欄留空就沿用記帳那一組）
# ===========================================================================
def _cfg(purpose: str) -> dict[str, str]:
    base = {
        "provider": (settings.model_provider or "openai").strip().lower(),
        "base_url": settings.model_base_url.strip(),
        "api_key": settings.model_api_key.strip(),
        "model": settings.model_name.strip(),
        "effort": settings.model_effort.strip(),
    }
    if purpose == "advice":
        over = {
            "provider": settings.advice_provider.strip().lower(),
            "base_url": settings.advice_base_url.strip(),
            "api_key": settings.advice_api_key.strip(),
            "model": settings.advice_model_name.strip(),
            "effort": settings.advice_effort.strip(),
        }
        base.update({k: v for k, v in over.items() if v})
    if base["provider"] == "anthropic" and not base["model"].startswith("claude-"):
        base["model"] = CLAUDE_DEFAULT
    return base


def is_configured(purpose: str = "parse") -> bool:
    c = _cfg(purpose)
    return bool(c["api_key"]) if c["provider"] == "anthropic" else bool(c["base_url"])


def model_name(purpose: str = "parse") -> str:
    """這次實際會用的模型名稱（寫進 nlp_parses.model_ver、advices.model_ver）。"""
    return _cfg(purpose)["model"]


# ===========================================================================
# 對外的兩支
# ===========================================================================
def complete(
    prompt: str,
    *,
    system: str = "",
    max_tokens: int = 512,
    temperature: float = 0.1,
    retries: int = 1,
    purpose: str = "parse",
    client: httpx.Client | None = None,
) -> str | None:
    """送一段 prompt，回模型寫的文字。沒設定模型服務回 None。"""
    out = _call(prompt, system=system, max_tokens=max_tokens, temperature=temperature,
                retries=retries, purpose=purpose, tool=None, schema=None, client=client)
    return None if out is None else out["text"]


def complete_json(
    prompt: str,
    *,
    tool: dict[str, Any] | None = None,
    schema: dict[str, Any] | None = None,
    purpose: str = "parse",
    **kwargs: Any,
) -> Any:
    """跟 complete 一樣，但要 JSON。

    tool    要模型用工具呼叫交出結果，回傳工具的參數（dict）
    schema  只要一段符合這個 JSON Schema 的 JSON（Claude 用 output_config.format、OpenAI 用 response_format 保證格式）
    模型常在 JSON 外面包 ```json，這裡會剝掉。解析不了丟 ModelError。
    """
    out = _call(prompt, tool=tool, schema=schema, purpose=purpose, **kwargs)
    if out is None:
        return None
    if out.get("args") is not None:
        return out["args"]
    return _parse_json_text(out["text"])


# ===========================================================================
# 內部
# ===========================================================================
def _call(prompt, *, system="", max_tokens=512, temperature=0.1, retries=1, purpose="parse",
          tool=None, schema=None, client=None):
    c = _cfg(purpose)
    if not (c["api_key"] if c["provider"] == "anthropic" else c["base_url"]):
        return None
    if c["provider"] == "anthropic":
        return _call_anthropic(c, prompt, system=system, max_tokens=max_tokens, retries=retries,
                               tool=tool, schema=schema)
    return _call_openai(c, prompt, system=system, max_tokens=max_tokens, temperature=temperature,
                        retries=retries, tool=tool, schema=schema, client=client)


def _call_openai(c, prompt, *, system, max_tokens, temperature, retries, tool, schema, client):
    url = c["base_url"].rstrip("/") + "/v1/chat/completions"
    headers = {"content-type": "application/json"}
    if c["api_key"]:
        headers["authorization"] = "Bearer " + c["api_key"]
    messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
    body: dict[str, Any] = {"model": c["model"], "messages": messages, "max_tokens": max_tokens,
                            "temperature": temperature}
    if tool:
        body["tools"] = [{"type": "function", "function": {
            "name": tool["name"], "description": tool.get("description", ""), "parameters": tool["input_schema"]}}]
        body["tool_choice"] = "required"
    elif schema:
        body["response_format"] = {"type": "json_schema",
                                   "json_schema": {"name": "result", "schema": schema, "strict": True}}

    own = client is None
    client = client or httpx.Client(timeout=settings.model_timeout_seconds)
    try:
        attempt = 0
        while attempt <= retries:
            try:
                res = client.post(url, json=body, headers=headers)
            except httpx.HTTPError as exc:
                if attempt < retries:
                    attempt += 1
                    time.sleep(0.5 * attempt)
                    continue
                raise ModelError("模型服務沒有回應：%s" % exc.__class__.__name__) from None
            if res.status_code >= 500 and attempt < retries:
                attempt += 1
                time.sleep(0.5 * attempt)
                continue
            if res.status_code == 400 and _adapt(body, res.text):
                continue                          # 這個服務不收某個參數：拿掉或換掉再送一次，不算重試
            if res.status_code != 200:
                raise ModelError("模型服務回 %d" % res.status_code)
            try:
                msg = res.json()["choices"][0]["message"]
            except (ValueError, KeyError, IndexError):
                raise ModelError("模型服務回來的格式看不懂") from None
            calls = msg.get("tool_calls") or []
            if tool and calls:
                raw = (calls[0].get("function") or {}).get("arguments")
                args = raw if isinstance(raw, dict) else _parse_json_text(raw or "")
                return {"text": msg.get("content") or "", "args": args}
            return {"text": msg.get("content") or "", "args": None}
    finally:
        if own:
            client.close()
    return None


def _adapt(body: dict[str, Any], error: str) -> bool:
    """OpenAI 相容的服務各自少支援一些參數。回 400 時看錯誤訊息，拿掉／換掉那個參數；改了回 True。

    · 推理型模型（例如 gpt-5 系列）不收 max_tokens、temperature：換成 max_completion_tokens、拿掉 temperature
      （思考也算在 max_completion_tokens 裡，所以順便放寬）
    · 不支援工具呼叫或結構化輸出的服務：拿掉，靠 prompt 裡「只回 JSON」與 _parse_json_text 接住
    """
    low = (error or "").lower()
    if "max_tokens" in low and "max_tokens" in body:
        body["max_completion_tokens"] = max(body.pop("max_tokens") * 4, 4096)
        return True
    if "temperature" in low and "temperature" in body:
        body.pop("temperature")
        return True
    if "response_format" in low and "response_format" in body:
        body.pop("response_format")
        return True
    if ("tool" in low or "function" in low) and "tools" in body:
        body.pop("tools")
        body.pop("tool_choice", None)
        return True
    return False


def _call_anthropic(c, prompt, *, system, max_tokens, retries, tool, schema):
    try:
        import anthropic
    except ImportError:
        raise ModelError("後端沒有安裝 anthropic 套件（pip install -r requirements.txt）") from None

    sdk = anthropic.Anthropic(api_key=c["api_key"], timeout=settings.model_timeout_seconds,
                              max_retries=retries)
    output_config: dict[str, Any] = {}
    if c["effort"] and not c["model"].startswith("claude-haiku-4"):
        output_config["effort"] = c["effort"]
    if schema and not tool:
        output_config["format"] = {"type": "json_schema", "schema": schema}

    kwargs: dict[str, Any] = {
        "model": c["model"],
        # Claude 會先思考再回答，這部分也算在 max_tokens 裡，給寬一點才不會被截斷
        "max_tokens": max(max_tokens * 4, 4096),
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        kwargs["system"] = system
    if tool:
        # 這幾顆模型不能強制指定工具（tool_choice 只能 auto），所以在 prompt 裡講清楚要用它；
        # strict 保證參數一定符合 schema
        kwargs["tools"] = [{"name": tool["name"], "description": tool.get("description", ""),
                            "strict": True, "input_schema": tool["input_schema"]}]
        kwargs["messages"] = [{"role": "user", "content":
                               prompt + "\n\n請用 %s 工具交出結果。" % tool["name"]}]
    extra: dict[str, Any] = {}
    if output_config:
        extra["output_config"] = output_config
    betas: list[str] = []
    if c["model"] in _CLAUDE_FALLBACK_MODELS:
        # 模型婉拒時，伺服器自動換一顆能回答的模型重跑——記帳的句子幾乎不會碰到，但開著不吃虧
        betas.append("server-side-fallback-2026-07-01")
        extra["fallbacks"] = "default"

    try:
        if betas:
            res = sdk.beta.messages.create(betas=betas, extra_body=extra or None, **kwargs)
        else:
            res = sdk.messages.create(extra_body=extra or None, **kwargs)
    except anthropic.AuthenticationError:
        raise ModelError("模型服務的金鑰不對（MODEL_API_KEY）") from None
    except anthropic.RateLimitError:
        raise ModelError("模型服務忙不過來，請稍後再試") from None
    except anthropic.APIStatusError as exc:
        raise ModelError("模型服務回 %d" % exc.status_code) from None
    except anthropic.APIConnectionError:
        raise ModelError("模型服務沒有回應") from None

    if res.stop_reason == "refusal":
        raise ModelError("模型拒絕處理這一段文字")
    text = "".join(b.text for b in res.content if getattr(b, "type", "") == "text")
    if tool:
        for b in res.content:
            if getattr(b, "type", "") == "tool_use" and b.name == tool["name"]:
                return {"text": text, "args": dict(b.input)}
    return {"text": text, "args": None}


def _parse_json_text(text: str) -> Any:
    raw = (text or "").strip()
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
