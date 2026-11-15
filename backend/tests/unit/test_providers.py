"""Provider adapters against recorded-format payloads (no network, no keys).

Gemini payloads match what the live API returned during Phase 3 probing. OpenAI and Anthropic
payloads follow their documented streaming formats.
"""

from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest

from app.core.config import Settings
from app.providers.embeddings import GeminiEmbeddings, build_embedder
from app.providers.http import ProviderError, ProviderNotConfigured
from app.providers.llm import (
    AnthropicLLM,
    FallbackLLM,
    GeminiLLM,
    GenerationParams,
    LLMMessage,
    OpenAILLM,
    complete,
)
from app.rag.profiles import PROFILES

PARAMS = GenerationParams()
MSGS = [LLMMessage("user", "Question?")]


def sse(*events: dict[str, object] | str) -> bytes:
    lines = []
    for event in events:
        lines.append(f"data: {event if isinstance(event, str) else json.dumps(event)}\n\n")
    return "".join(lines).encode()


def client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_gemini_stream_skips_thoughts_and_reports_usage() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["key"] = request.headers.get("x-goog-api-key")
        seen["body"] = json.loads(request.content)
        body = sse(
            {"candidates": [{"content": {"parts": [{"text": "thinking...", "thought": True}]}}]},
            {"candidates": [{"content": {"parts": [{"text": "Leave is 20 days "}]}}]},
            {
                "candidates": [{"content": {"parts": [{"text": "[1]."}]}}],
                "usageMetadata": {
                    "promptTokenCount": 36,
                    "candidatesTokenCount": 8,
                    "thoughtsTokenCount": 5,
                },
            },
        )
        return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})

    llm = GeminiLLM("gemini-3.5-flash-lite", "k-123", client(handler), thinking_level="minimal")
    result = await complete(llm, "system", MSGS, PARAMS)
    assert result.text == "Leave is 20 days [1]."
    assert (result.usage.input_tokens, result.usage.output_tokens) == (36, 13)
    assert "streamGenerateContent?alt=sse" in str(seen["url"])
    assert seen["key"] == "k-123"
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "minimal"}
    assert body["systemInstruction"]["parts"][0]["text"] == "system"


async def test_openai_stream_contract() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer sk-x"
        payload = json.loads(request.content)
        assert payload["messages"][0] == {"role": "system", "content": "system"}
        assert payload["stream_options"] == {"include_usage": True}
        return httpx.Response(
            200,
            content=sse(
                {"choices": [{"delta": {"content": "Hello "}}]},
                {"choices": [{"delta": {"content": "[1]"}}]},
                {"choices": [], "usage": {"prompt_tokens": 10, "completion_tokens": 3}},
                "[DONE]",
            ),
        )

    result = await complete(OpenAILLM("gpt-x", "sk-x", client(handler)), "system", MSGS, PARAMS)
    assert result.text == "Hello [1]"
    assert (result.usage.input_tokens, result.usage.output_tokens) == (10, 3)


async def test_anthropic_stream_contract() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-api-key"] == "ak"
        assert request.headers["anthropic-version"] == "2023-06-01"
        assert json.loads(request.content)["system"] == "system"
        return httpx.Response(
            200,
            content=sse(
                {"type": "message_start", "message": {"usage": {"input_tokens": 12}}},
                {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Answer "}},
                {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "[2]"}},
                {"type": "message_delta", "usage": {"output_tokens": 4}},
                {"type": "message_stop"},
            ),
        )

    result = await complete(AnthropicLLM("claude-x", "ak", client(handler)), "system", MSGS, PARAMS)
    assert result.text == "Answer [2]"
    assert (result.usage.input_tokens, result.usage.output_tokens) == (12, 4)


async def test_auth_errors_are_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(401, json={"error": {"message": "bad key"}})

    with pytest.raises(ProviderError) as err:
        await complete(GeminiLLM("m", "bad", client(handler), None), "s", MSGS, PARAMS)
    assert err.value.status == 401 and not err.value.retryable
    assert calls["n"] == 1


async def test_overload_retries_then_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.providers.llm.backoff", lambda attempt: 0)
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        model = "primary" if "primary" in str(request.url) else "fallback"
        calls.append(model)
        if model == "primary":
            return httpx.Response(503, json={"error": {"message": "high demand"}})
        return httpx.Response(
            200, content=sse({"candidates": [{"content": {"parts": [{"text": "ok [1]"}]}}]})
        )

    http = client(handler)
    llm = FallbackLLM(
        [GeminiLLM("primary", "k", http, None), GeminiLLM("fallback", "k", http, None)]
    )
    result = await complete(llm, "s", MSGS, PARAMS)
    assert result.text == "ok [1]"
    assert calls == ["primary", "primary", "primary", "fallback"]


async def test_gemini_embeddings_batch_and_normalize() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert all(
            r["taskType"] == "RETRIEVAL_QUERY" and r["outputDimensionality"] == 768
            for r in body["requests"]
        )
        return httpx.Response(
            200, json={"embeddings": [{"values": [3.0, 4.0]} for _ in body["requests"]]}
        )

    emb = GeminiEmbeddings(PROFILES[2], "k", client(handler))
    vectors = await emb.embed(["a", "b"], "query")
    assert vectors == [[0.6, 0.8], [0.6, 0.8]]


def test_missing_key_is_reported_clearly() -> None:
    settings = Settings(
        database_url="postgresql+psycopg://x/y", secret_key="s" * 40, gemini_api_key="  "
    )  # type: ignore[arg-type]
    with pytest.raises(ProviderNotConfigured):
        build_embedder(settings, 2, httpx.AsyncClient())
