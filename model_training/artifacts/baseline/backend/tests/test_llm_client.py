"""Regression tests for the shared model transport and JSON parser."""

import os

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production-at-least-32-bytes-long")

import httpx
import pytest

from app.services.llm import client as llm
from app.toolkit.config import settings


@pytest.fixture(autouse=True)
def model_settings(monkeypatch):
    monkeypatch.setattr(settings, "model_base_url", " http://model.test/ ")
    monkeypatch.setattr(settings, "model_timeout_seconds", 7.0)


def response(content):
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


@pytest.mark.parametrize("payload", [None, [], {"choices": None}, {"choices": []},
    {"choices": [None]}, {"choices": [{"message": None}]},
    {"choices": [{"message": {}}]}])
def test_malformed_envelope_is_model_error(payload):
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=payload))) as fake:
        with pytest.raises(llm.ModelError):
            llm.complete("hi", client=fake)
        assert not fake.is_closed


@pytest.mark.parametrize("content", [None, 42, {}, [], "", "  \n"])
def test_invalid_content_is_model_error(content):
    with httpx.Client(transport=httpx.MockTransport(lambda r: response(content))) as fake:
        with pytest.raises(llm.ModelError):
            llm.complete_json("hi", client=fake)


@pytest.mark.parametrize("text, expected", [
    ('```json\n{"amount": 80}\n```', {"amount": 80}),
    ('說明：{"items": [1, 2]}\n補充 [注意]', {"items": [1, 2]}),
    ('[{"note": "a } and [ b"}] trailing }', [{"note": "a } and [ b"}]),
])
def test_json_wrappers(text, expected):
    with httpx.Client(transport=httpx.MockTransport(lambda r: response(text))) as fake:
        assert llm.complete_json("hi", client=fake) == expected


@pytest.mark.parametrize("text", ['no json', '{"amount":', '{bad} {"amount": 80}'])
def test_invalid_json_is_model_error(text):
    with httpx.Client(transport=httpx.MockTransport(lambda r: response(text))) as fake:
        with pytest.raises(llm.ModelError):
            llm.complete_json("hi", client=fake)


@pytest.mark.parametrize("retries", [-1, 1.5, True])
def test_invalid_retry_count(retries):
    with pytest.raises(ValueError, match="retries"):
        llm.complete("hi", retries=retries)


def test_retry_recovery_timeout_and_client_ownership(monkeypatch):
    calls, sleeps = [], []
    monkeypatch.setattr(llm.time, "sleep", sleeps.append)

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            raise httpx.ReadTimeout("timeout", request=request)
        if len(calls) == 2:
            return httpx.Response(503)
        return response("ok")

    with httpx.Client(transport=httpx.MockTransport(handler), timeout=None) as fake:
        assert llm.complete("hi", client=fake, retries=2) == "ok"
        assert not fake.is_closed
    assert sleeps == [0.5, 1.0]
    assert str(calls[0].url) == "http://model.test/v1/chat/completions"
    assert calls[0].extensions["timeout"]["read"] == 7.0


def test_owned_client_closes_after_error(monkeypatch):
    fake = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(400)))
    monkeypatch.setattr(llm.httpx, "Client", lambda **kwargs: fake)
    with pytest.raises(llm.ModelError):
        llm.complete("hi")
    assert fake.is_closed


def test_unconfigured_skips_request(monkeypatch):
    monkeypatch.setattr(settings, "model_base_url", "  ")
    assert llm.complete("hi") is None
    assert llm.complete_json("hi") is None
