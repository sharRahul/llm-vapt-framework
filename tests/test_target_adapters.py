from __future__ import annotations

import pytest

from core.scanner import Scanner
from integrations.target_adapters import invoke_target, normalize_target_config


class FakeResponse:
    def __init__(self, payload, status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code
        self.headers = {"content-type": "application/json"}

    @property
    def text(self) -> str:
        import json

        return json.dumps(self.payload)

    def json(self):
        return self.payload


def _invoke(monkeypatch, config: dict, payload: dict) -> str:
    captured: dict = {}

    def fake_request(method, url, **kwargs):
        captured["method"] = method
        captured["url"] = url
        captured["json"] = kwargs.get("json")
        captured["params"] = kwargs.get("params")
        return FakeResponse(payload)

    monkeypatch.setattr("integrations.target_adapters.requests.request", fake_request)
    result = invoke_target("t", normalize_target_config("t", config), "test")
    assert result.ok, result.error
    _invoke.captured = captured  # type: ignore[attr-defined]
    return result.answer


def test_chat_completions_target_normalises_response(monkeypatch) -> None:
    answer = _invoke(
        monkeypatch,
        {"type": "chat_completions", "base_url": "http://127.0.0.1", "endpoint_path": "/chat", "model": "demo"},
        {"choices": [{"message": {"content": "hello"}}]},
    )
    assert answer == "hello"


def test_ollama_target_normalises_response(monkeypatch) -> None:
    answer = _invoke(
        monkeypatch,
        {"type": "ollama_generate", "base_url": "http://127.0.0.1", "endpoint_path": "/api/generate", "model": "demo"},
        {"response": "ollama output"},
    )
    assert answer == "ollama output"


def test_webhook_target_returns_whole_body_without_extraction_path(monkeypatch) -> None:
    answer = _invoke(
        monkeypatch,
        {"type": "webhook_json", "base_url": "http://127.0.0.1", "endpoint_path": "/hook"},
        {"output": "webhook output"},
    )
    assert "webhook output" in answer


def test_http_json_target_uses_configured_extraction_path(monkeypatch) -> None:
    answer = _invoke(
        monkeypatch,
        {
            "type": "http_json",
            "base_url": "http://127.0.0.1",
            "endpoint_path": "/ask",
            "request_body_template": {"msg": "{{prompt}}"},
            "response_extraction_path": "data.reply",
        },
        {"data": {"reply": "extracted"}},
    )
    assert answer == "extracted"


def test_get_target_sends_prompt_as_query_parameters(monkeypatch) -> None:
    _invoke(
        monkeypatch,
        {
            "type": "http_json",
            "base_url": "http://127.0.0.1",
            "endpoint_path": "/get",
            "method": "GET",
            "request_body_template": {"msg": "{{prompt}}"},
        },
        {"reply": "ok"},
    )
    captured = _invoke.captured  # type: ignore[attr-defined]
    assert captured["method"] == "GET"
    assert captured["params"] == {"msg": "test"}
    assert captured["json"] is None


def test_placeholder_target_rejected_even_when_authorised() -> None:
    with pytest.raises(ValueError):
        Scanner().scan(target_name="local_chat_completions", profile_name="baseline", authorised=True)
