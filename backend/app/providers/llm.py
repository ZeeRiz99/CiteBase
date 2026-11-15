"""LLM providers behind one streaming interface.

- GeminiLLM: verified against the live API (streamGenerateContent SSE, usage, thinking level).
- OpenAILLM / AnthropicLLM: built to their documented streaming contracts and covered by
  contract tests with recorded-format payloads; not live-verified here (no keys configured).
- FakeLLM: deterministic, offline; answers from the first matching source with a citation.

Retries happen only before the first token; after that a failure surfaces to the caller.
"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

import httpx

from app.core.config import Settings
from app.providers.http import ProviderError, ProviderNotConfigured, backoff, error_from_response
from app.rag.constants import REFUSAL_TEXT

Role = Literal["user", "assistant"]


@dataclass(frozen=True)
class LLMMessage:
    role: Role
    content: str


@dataclass
class LLMUsage:
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    kind: str = "chat"  # what the call was for (set by the caller): chat, rewrite, regenerate...


@dataclass
class LLMChunk:
    text: str = ""
    usage: LLMUsage | None = None


@dataclass
class LLMResult:
    text: str
    usage: LLMUsage


@dataclass(frozen=True)
class GenerationParams:
    temperature: float = 0.1
    max_tokens: int = 1024
    json_output: bool = False


class LLMProvider(Protocol):
    name: str
    model: str

    def stream(
        self, system: str, messages: list[LLMMessage], params: GenerationParams
    ) -> AsyncGenerator[LLMChunk, None]: ...


async def complete(
    llm: LLMProvider, system: str, messages: list[LLMMessage], params: GenerationParams
) -> LLMResult:
    parts: list[str] = []
    usage = LLMUsage(model=llm.model)
    async for chunk in llm.stream(system, messages, params):
        parts.append(chunk.text)
        if chunk.usage:
            usage = chunk.usage
    return LLMResult(text="".join(parts), usage=usage)


async def _sse_lines(response: httpx.Response) -> AsyncIterator[str]:
    async for raw in response.aiter_lines():
        line = raw.strip()
        if line.startswith("data:"):
            payload = line[5:].strip()
            if payload and payload != "[DONE]":
                yield payload


class _StreamingHTTP:
    """Opens a streaming POST with retries before the first byte of body is consumed."""

    name = "http"
    attempts = 3

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def _open(
        self, url: str, body: dict[str, Any], headers: dict[str, str]
    ) -> httpx.Response:
        last: ProviderError | None = None
        for attempt in range(self.attempts):
            request = self._client.build_request("POST", url, json=body, headers=headers)
            try:
                response = await self._client.send(request, stream=True)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last = ProviderError(
                    self.name, f"network error: {type(exc).__name__}", retryable=True
                )
            else:
                if response.is_success:
                    return response
                await response.aread()
                await response.aclose()
                last = error_from_response(self.name, response)
                if not last.retryable:
                    raise last
            if attempt < self.attempts - 1:
                await asyncio.sleep(backoff(attempt))
        assert last is not None
        raise last


class GeminiLLM(_StreamingHTTP):
    name = "gemini"
    URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?alt=sse"

    def __init__(
        self, model: str, api_key: str, client: httpx.AsyncClient, thinking_level: str | None
    ) -> None:
        super().__init__(client)
        self.model = model
        self._key = api_key
        self._thinking = thinking_level

    async def stream(
        self, system: str, messages: list[LLMMessage], params: GenerationParams
    ) -> AsyncGenerator[LLMChunk, None]:
        config: dict[str, Any] = {
            "temperature": params.temperature,
            "maxOutputTokens": params.max_tokens,
        }
        if self._thinking and self.model.startswith("gemini-3"):
            config["thinkingConfig"] = {"thinkingLevel": self._thinking}
        if params.json_output:
            config["responseMimeType"] = "application/json"
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [
                {
                    "role": "model" if m.role == "assistant" else "user",
                    "parts": [{"text": m.content}],
                }
                for m in messages
            ],
            "generationConfig": config,
        }
        response = await self._open(
            self.URL.format(model=self.model), body, {"x-goog-api-key": self._key}
        )
        usage = LLMUsage(model=self.model)
        try:
            async for payload in _sse_lines(response):
                data = json.loads(payload)
                for candidate in data.get("candidates", [])[:1]:
                    for part in (candidate.get("content") or {}).get("parts", []):
                        if part.get("text") and not part.get("thought"):
                            yield LLMChunk(text=part["text"])
                meta = data.get("usageMetadata")
                if meta:
                    usage = LLMUsage(
                        model=self.model,
                        input_tokens=int(meta.get("promptTokenCount", 0)),
                        output_tokens=int(meta.get("candidatesTokenCount", 0))
                        + int(meta.get("thoughtsTokenCount", 0)),
                    )
        finally:
            await response.aclose()
        yield LLMChunk(usage=usage)


class OpenAILLM(_StreamingHTTP):
    name = "openai"
    URL = "https://api.openai.com/v1/chat/completions"

    def __init__(self, model: str, api_key: str, client: httpx.AsyncClient) -> None:
        super().__init__(client)
        self.model = model
        self._key = api_key

    async def stream(
        self, system: str, messages: list[LLMMessage], params: GenerationParams
    ) -> AsyncGenerator[LLMChunk, None]:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}]
            + [{"role": m.role, "content": m.content} for m in messages],
            "temperature": params.temperature,
            "max_completion_tokens": params.max_tokens,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if params.json_output:
            body["response_format"] = {"type": "json_object"}
        response = await self._open(self.URL, body, {"Authorization": f"Bearer {self._key}"})
        usage = LLMUsage(model=self.model)
        try:
            async for payload in _sse_lines(response):
                data = json.loads(payload)
                for choice in data.get("choices", [])[:1]:
                    text = (choice.get("delta") or {}).get("content")
                    if text:
                        yield LLMChunk(text=text)
                if data.get("usage"):
                    usage = LLMUsage(
                        model=self.model,
                        input_tokens=int(data["usage"].get("prompt_tokens", 0)),
                        output_tokens=int(data["usage"].get("completion_tokens", 0)),
                    )
        finally:
            await response.aclose()
        yield LLMChunk(usage=usage)


class AnthropicLLM(_StreamingHTTP):
    name = "anthropic"
    URL = "https://api.anthropic.com/v1/messages"
    VERSION = "2023-06-01"

    def __init__(self, model: str, api_key: str, client: httpx.AsyncClient) -> None:
        super().__init__(client)
        self.model = model
        self._key = api_key

    async def stream(
        self, system: str, messages: list[LLMMessage], params: GenerationParams
    ) -> AsyncGenerator[LLMChunk, None]:
        body = {
            "model": self.model,
            "system": system,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": params.max_tokens,
            "temperature": params.temperature,
            "stream": True,
        }
        headers = {"x-api-key": self._key, "anthropic-version": self.VERSION}
        response = await self._open(self.URL, body, headers)
        usage = LLMUsage(model=self.model)
        try:
            async for payload in _sse_lines(response):
                data = json.loads(payload)
                kind = data.get("type")
                if kind == "message_start":
                    usage.input_tokens = int(
                        data["message"].get("usage", {}).get("input_tokens", 0)
                    )
                elif kind == "content_block_delta" and data["delta"].get("type") == "text_delta":
                    yield LLMChunk(text=data["delta"]["text"])
                elif kind == "message_delta":
                    usage.output_tokens = int(data.get("usage", {}).get("output_tokens", 0))
        finally:
            await response.aclose()
        yield LLMChunk(usage=usage)


class FallbackLLM:
    """Try the primary model, then fallbacks, when a provider is overloaded before streaming."""

    def __init__(self, chain: list[LLMProvider]) -> None:
        self.chain = chain
        self.name = chain[0].name
        self.model = chain[0].model

    async def stream(
        self, system: str, messages: list[LLMMessage], params: GenerationParams
    ) -> AsyncGenerator[LLMChunk, None]:
        for index, llm in enumerate(self.chain):
            started = False
            try:
                async for chunk in llm.stream(system, messages, params):
                    started = True
                    yield chunk
                return
            except ProviderError as exc:
                if started or not exc.retryable or index == len(self.chain) - 1:
                    raise


_SOURCE = re.compile(r'<source id="(\d+)"[^>]*>(.*?)</source>', re.S)
_WORDS = re.compile(r"[a-z0-9]{3,}")

Responder = Callable[[str, list[LLMMessage]], Awaitable[str] | str]


@dataclass
class FakeLLM:
    """Deterministic offline model for tests.

    Default behaviour: pick the source sharing the most words with the question and answer with
    its first sentence plus a citation; with no sources, return the refusal sentence.
    """

    model: str = "fake-llm"
    name: str = "fake"
    responder: Responder | None = None
    calls: list[tuple[str, list[LLMMessage]]] = field(default_factory=list)

    async def _answer(self, system: str, messages: list[LLMMessage]) -> str:
        if self.responder is not None:
            result = self.responder(system, messages)
            return await result if not isinstance(result, str) else result
        prompt = messages[-1].content
        question = prompt.split("<sources>")[0].lower()
        sources = _SOURCE.findall(prompt)
        if not sources:
            return REFUSAL_TEXT
        q_words = set(_WORDS.findall(question))
        best = max(sources, key=lambda s: len(q_words & set(_WORDS.findall(s[1].lower()))))
        first_sentence = re.split(r"(?<=[.!?])\s", best[1].strip())[0]
        return f"{first_sentence} [{best[0]}]"

    async def stream(
        self, system: str, messages: list[LLMMessage], params: GenerationParams
    ) -> AsyncGenerator[LLMChunk, None]:
        self.calls.append((system, messages))
        text = await self._answer(system, messages)
        for word in re.findall(r"\S+\s*", text):
            yield LLMChunk(text=word)
        yield LLMChunk(
            usage=LLMUsage(
                model=self.model,
                input_tokens=len(messages[-1].content) // 4,
                output_tokens=len(text) // 4,
            )
        )


def _key(setting: Any) -> str:
    return setting.get_secret_value().strip() if setting else ""


def build_llm(
    settings: Settings, client: httpx.AsyncClient, *, model: str | None = None
) -> LLMProvider:
    """The configured provider for `model` (default: the answer model), with fallbacks."""
    if settings.llm_backend == "fake":
        return FakeLLM()
    models = [model] if model else [settings.llm_model, *settings.llm_fallback_models]
    provider = settings.llm_provider
    if provider == "gemini":
        key = _key(settings.gemini_api_key)
        if not key:
            raise ProviderNotConfigured("gemini")
        chain: list[LLMProvider] = [
            GeminiLLM(m, key, client, settings.llm_thinking_level) for m in models
        ]
    elif provider == "openai":
        key = _key(settings.openai_api_key)
        if not key:
            raise ProviderNotConfigured("openai")
        chain = [OpenAILLM(m, key, client) for m in models]
    else:
        key = _key(settings.anthropic_api_key)
        if not key:
            raise ProviderNotConfigured("anthropic")
        chain = [AnthropicLLM(m, key, client) for m in models]
    return chain[0] if len(chain) == 1 else FallbackLLM(chain)
