"""Embedding provider interface, Azure OpenAI implementation and a caching decorator."""
from __future__ import annotations

import abc
import json

import httpx

from app.config import Settings
from app.core.errors import ConfigurationError
from app.core.retry import raise_for_status, with_retry
from app.core.text import count_tokens, sha256
from app.core.usage import TokenBudget, UsageRecord, record_usage
from app.pipeline.cache import CacheBackend


class EmbeddingProvider(abc.ABC):
    model: str = ""
    dimensions: int = 0

    @abc.abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts (order preserved)."""

    async def aclose(self) -> None:  # pragma: no cover
        return None


class AzureOpenAIEmbeddings(EmbeddingProvider):
    def __init__(self, settings: Settings, budget: TokenBudget | None = None):
        if not settings.azure_openai_endpoint or not settings.azure_openai_api_key.get_secret_value():
            raise ConfigurationError("Azure OpenAI is not configured.")
        self.s = settings
        self.model = settings.embedding_model
        self.dimensions = settings.embedding_dimensions
        self.budget = budget
        self._client = httpx.AsyncClient(
            base_url=settings.azure_openai_endpoint.rstrip("/"),
            headers={"api-key": settings.azure_openai_api_key.get_secret_value()},
            timeout=settings.upstream_timeout_seconds,
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        bs = max(1, self.s.embedding_batch_size)
        url = f"/openai/deployments/{self.model}/embeddings?api-version={self.s.azure_openai_api_version}"
        for i in range(0, len(texts), bs):
            batch = texts[i : i + bs]
            body: dict = {"input": batch}
            if self.model.startswith("text-embedding-3"):
                body["dimensions"] = self.dimensions

            async def call(body=body) -> dict:
                resp = await self._client.post(url, json=body)
                raise_for_status(resp)
                return resp.json()

            data = await with_retry(call, max_retries=self.s.upstream_max_retries + 2, op="embeddings")
            items = sorted(data["data"], key=lambda d: d["index"])
            out.extend(d["embedding"] for d in items)
            tokens = (data.get("usage") or {}).get("prompt_tokens") or sum(count_tokens(t) for t in batch)
            record_usage(UsageRecord("embedding", self.model, tokens, 0), self.budget)
        return out

    async def aclose(self) -> None:
        await self._client.aclose()


class CachedEmbeddings(EmbeddingProvider):
    """Caches query embeddings (repeated questions are common: 'hostel timings', 'fee')."""

    def __init__(self, inner: EmbeddingProvider, cache: CacheBackend, ttl: int):
        self.inner, self.cache, self.ttl = inner, cache, ttl
        self.model, self.dimensions = inner.model, inner.dimensions

    def _key(self, text: str) -> str:
        return f"emb:{self.model}:{self.dimensions}:{sha256(text)}"

    async def embed(self, texts: list[str]) -> list[list[float]]:
        results: list[list[float] | None] = []
        missing: list[int] = []
        for i, t in enumerate(texts):
            hit = await self.cache.get(self._key(t))
            results.append(json.loads(hit) if hit else None)
            if hit is None:
                missing.append(i)
        if missing:
            # de-duplicate within the batch
            uniq = list(dict.fromkeys(texts[i] for i in missing))
            vecs = await self.inner.embed(uniq)
            by_text = dict(zip(uniq, vecs))
            for i in missing:
                results[i] = by_text[texts[i]]
            for t, v in by_text.items():
                await self.cache.set(self._key(t), json.dumps(v), self.ttl)
        return [r for r in results if r is not None]

    async def aclose(self) -> None:
        await self.inner.aclose()


def build_embeddings(settings: Settings, budget: TokenBudget | None = None) -> EmbeddingProvider:
    if settings.embedding_provider == "mock" or settings.mock_azure:
        from app.services.mock.embeddings import MockEmbeddings

        return MockEmbeddings(settings.embedding_dimensions)
    if settings.embedding_provider == "azure_openai":
        return AzureOpenAIEmbeddings(settings, budget)
    raise ConfigurationError(f"Unknown embedding provider {settings.embedding_provider}")

