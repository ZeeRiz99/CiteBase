"""Embedding providers behind one interface. Each is bound to an EmbeddingProfile.

- GeminiEmbeddings: verified against the live API (batchEmbedContents, task types, 768 dims).
- OpenAIEmbeddings: built to the documented /v1/embeddings contract; not live-verified here.
- LocalEmbeddings: the embedder service (multilingual-e5-small, ONNX) in Compose.
- FakeEmbeddings: deterministic hashed bag-of-words vectors for tests (shared words, close vectors).
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Literal, Protocol

import httpx

from app.core.config import Settings
from app.providers.http import ProviderNotConfigured, post_json
from app.rag.profiles import EmbeddingProfile, get_profile

Kind = Literal["document", "query"]


class EmbeddingProvider(Protocol):
    profile: EmbeddingProfile

    async def embed(self, texts: list[str], kind: Kind) -> list[list[float]]: ...


def l2_normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vector)) or 1.0
    return [x / norm for x in vector]


def _batches(items: list[str], size: int) -> list[list[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


class GeminiEmbeddings:
    BATCH = 100
    URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:batchEmbedContents"

    def __init__(self, profile: EmbeddingProfile, api_key: str, client: httpx.AsyncClient) -> None:
        self.profile = profile
        self._key = api_key
        self._client = client

    async def embed(self, texts: list[str], kind: Kind) -> list[list[float]]:
        task = "RETRIEVAL_DOCUMENT" if kind == "document" else "RETRIEVAL_QUERY"
        model = f"models/{self.profile.model}"
        out: list[list[float]] = []
        for batch in _batches(texts, self.BATCH):
            body = {
                "requests": [
                    {
                        "model": model,
                        "content": {"parts": [{"text": text}]},
                        "taskType": task,
                        "outputDimensionality": self.profile.dimension,
                    }
                    for text in batch
                ]
            }
            response = await post_json(
                self._client,
                "gemini",
                self.URL.format(model=self.profile.model),
                json=body,
                headers={"x-goog-api-key": self._key},
            )
            out.extend(l2_normalize(e["values"]) for e in response.json()["embeddings"])
        return out


class OpenAIEmbeddings:
    BATCH = 256
    URL = "https://api.openai.com/v1/embeddings"

    def __init__(self, profile: EmbeddingProfile, api_key: str, client: httpx.AsyncClient) -> None:
        self.profile = profile
        self._key = api_key
        self._client = client

    async def embed(self, texts: list[str], kind: Kind) -> list[list[float]]:
        out: list[list[float]] = []
        for batch in _batches(texts, self.BATCH):
            response = await post_json(
                self._client,
                "openai",
                self.URL,
                json={
                    "model": self.profile.model,
                    "input": batch,
                    "dimensions": self.profile.dimension,
                },
                headers={"Authorization": f"Bearer {self._key}"},
            )
            data = sorted(response.json()["data"], key=lambda d: d["index"])
            out.extend(l2_normalize(d["embedding"]) for d in data)
        return out


class LocalEmbeddings:
    BATCH = 32

    def __init__(self, profile: EmbeddingProfile, base_url: str, client: httpx.AsyncClient) -> None:
        self.profile = profile
        self._url = base_url.rstrip("/") + "/embed"
        self._client = client

    async def embed(self, texts: list[str], kind: Kind) -> list[list[float]]:
        prefix = self.profile.query_prefix if kind == "query" else self.profile.passage_prefix
        out: list[list[float]] = []
        for batch in _batches(texts, self.BATCH):
            response = await post_json(
                self._client,
                "local-embedder",
                self._url,
                json={"texts": [prefix + t for t in batch]},
                headers={},
            )
            out.extend(response.json()["vectors"])
        return out


_WORD = re.compile(r"[a-z0-9]+")


def _stem(word: str) -> str:
    for suffix in ("ing", "es", "s", "ed"):
        if len(word) > 4 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


class FakeEmbeddings:
    """Deterministic and offline. Shared words produce high cosine similarity."""

    def __init__(self, profile: EmbeddingProfile) -> None:
        self.profile = profile
        self.calls = 0

    def vector(self, text: str) -> list[float]:
        vec = [0.0] * self.profile.dimension
        for word in _WORD.findall(text.lower()):
            if len(word) < 3:
                continue
            digest = hashlib.sha1(_stem(word).encode()).digest()  # noqa: S324 - not security
            index = int.from_bytes(digest[:4], "big") % self.profile.dimension
            vec[index] += 1.0 if digest[4] % 2 else -1.0
        if not any(vec):
            vec[0] = 1.0
        return l2_normalize(vec)

    async def embed(self, texts: list[str], kind: Kind) -> list[list[float]]:
        self.calls += 1
        return [self.vector(t) for t in texts]


def build_embedder(
    settings: Settings, profile_id: int, client: httpx.AsyncClient
) -> EmbeddingProvider:
    profile = get_profile(profile_id)
    if settings.embedding_backend == "fake":
        return FakeEmbeddings(profile)
    if profile.provider == "local":
        return LocalEmbeddings(profile, settings.embedder_url, client)
    key_setting = (
        settings.gemini_api_key if profile.provider == "gemini" else settings.openai_api_key
    )
    key = key_setting.get_secret_value().strip() if key_setting else ""
    if not key:
        raise ProviderNotConfigured(profile.provider)
    if profile.provider == "gemini":
        return GeminiEmbeddings(profile, key, client)
    return OpenAIEmbeddings(profile, key, client)
