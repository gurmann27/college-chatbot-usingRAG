"""Search index interface + Azure AI Search (REST) implementation.

Hybrid retrieval is done as separate BM25 and vector queries whose ranked lists are
fused client-side with RRF (see ``pipeline.retrieval``). This keeps fusion testable,
lets us use two query vectors (original + English), and works on the Free tier.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass

import httpx

from app.config import Settings
from app.core.errors import ConfigurationError
from app.core.retry import raise_for_status, with_retry
from app.schemas import Chunk

SELECT_FIELDS = (
    "id,document_id,document_name,page,content,section_title,category,effective_date,version,language,content_hash,blob_name"
)


@dataclass
class SearchHit:
    chunk: Chunk
    score: float  # BM25 for keyword hits, cosine similarity (-1..1) for vector hits
    reranker_score: float | None = None  # raw Azure semantic score (0..4)


def odata_str(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def build_filter(document_ids: list[str] | None = None, category: str | None = None) -> str | None:
    parts: list[str] = []
    if document_ids:
        safe = [d for d in document_ids if d and "," not in d]
        if safe:
            parts.append(f"search.in(document_id, {odata_str(','.join(safe))}, ',')")
    if category:
        parts.append(f"category eq {odata_str(category)}")
    return " and ".join(parts) or None


class SearchIndex(abc.ABC):
    @abc.abstractmethod
    async def keyword_search(
        self, text: str, *, filter: str | None, top: int, semantic: bool = False
    ) -> list[SearchHit]: ...

    @abc.abstractmethod
    async def vector_search(self, vector: list[float], *, filter: str | None, top: int) -> list[SearchHit]: ...

    @abc.abstractmethod
    async def upsert(self, docs: list[dict]) -> None:
        """Upload / merge index documents (dicts with all index fields incl. content_vector)."""

    @abc.abstractmethod
    async def delete_document(self, document_id: str) -> int:
        """Delete every chunk of a document. Returns number of chunks deleted."""

    async def aclose(self) -> None:  # pragma: no cover
        return None


def azure_score_to_cosine(score: float) -> float:
    """Azure AI Search returns 1/(1+distance) for cosine, distance = 1-cos."""
    if score <= 0:
        return 0.0
    return 1.0 - (1.0 / score - 1.0)


class AzureSearchIndex(SearchIndex):
    def __init__(self, settings: Settings):
        if not settings.azure_search_endpoint or not settings.azure_search_api_key.get_secret_value():
            raise ConfigurationError("Azure AI Search is not configured.")
        self.s = settings
        self._client = httpx.AsyncClient(
            base_url=settings.azure_search_endpoint.rstrip("/"),
            headers={"api-key": settings.azure_search_api_key.get_secret_value()},
            timeout=settings.upstream_timeout_seconds,
        )
        self._docs = f"/indexes/{settings.azure_search_index}/docs"
        self._v = f"api-version={settings.azure_search_api_version}"

    async def _post(self, path: str, body: dict, op: str) -> dict:
        async def call() -> dict:
            resp = await self._client.post(f"{self._docs}/{path}?{self._v}", json=body)
            raise_for_status(resp)
            return resp.json()

        return await with_retry(call, max_retries=self.s.upstream_max_retries, op=op)

    @staticmethod
    def _to_chunk(d: dict) -> Chunk:
        return Chunk(**{k: d.get(k) for k in Chunk.model_fields if k in d})

    async def keyword_search(self, text, *, filter, top, semantic=False) -> list[SearchHit]:
        body: dict = {"search": text, "top": top, "select": SELECT_FIELDS, "searchFields": "content,document_name,section_title"}
        if filter:
            body["filter"] = filter
        if semantic:
            body.update({"queryType": "semantic", "semanticConfiguration": self.s.semantic_config_name})
        data = await self._post("search", body, "search:keyword")
        return [
            SearchHit(self._to_chunk(d), float(d.get("@search.score") or 0), d.get("@search.rerankerScore"))
            for d in data.get("value", [])
        ]

    async def vector_search(self, vector, *, filter, top) -> list[SearchHit]:
        body: dict = {
            "select": SELECT_FIELDS,
            "top": top,
            "vectorQueries": [{"kind": "vector", "vector": vector, "fields": "content_vector", "k": top}],
        }
        if filter:
            body["filter"] = filter
            body["vectorFilterMode"] = "preFilter"
        data = await self._post("search", body, "search:vector")
        return [
            SearchHit(self._to_chunk(d), azure_score_to_cosine(float(d.get("@search.score") or 0)))
            for d in data.get("value", [])
        ]

    async def upsert(self, docs: list[dict]) -> None:
        for i in range(0, len(docs), 500):  # 1000 docs / 16 MB per batch limit
            batch = [{"@search.action": "mergeOrUpload", **d} for d in docs[i : i + 500]]
            await self._post("index", {"value": batch}, "search:upsert")

    async def delete_document(self, document_id: str) -> int:
        deleted = 0
        for _ in range(100):  # guard against eventual-consistency loops
            data = await self._post(
                "search",
                {"search": "*", "filter": f"document_id eq {odata_str(document_id)}", "select": "id", "top": 1000},
                "search:list",
            )
            ids = [d["id"] for d in data.get("value", [])]
            if not ids:
                return deleted
            await self._post(
                "index", {"value": [{"@search.action": "delete", "id": i} for i in ids]}, "search:delete"
            )
            deleted += len(ids)
        return deleted

    async def aclose(self) -> None:
        await self._client.aclose()


def build_search(settings: Settings) -> SearchIndex:
    if settings.mock_azure:
        from app.services.mock.search import InMemorySearchIndex

        return InMemorySearchIndex()
    return AzureSearchIndex(settings)
