"""Step (c): cross-lingual hybrid retrieval with reciprocal rank fusion.

* embeds BOTH the original query and the English rendering (one batched call)
* BM25 keyword query on the English text + one vector query per embedding
* fuses the ranked lists with RRF, keeps the top ``retrieval_top_k``
* resolves conflicting versions: when several versions/circulars of the same document
  family are retrieved, only the one with the latest effective_date is kept
"""
from __future__ import annotations

import asyncio
import re
from collections import defaultdict
from typing import Iterable

from app.config import Settings
from app.core.text import term_coverage
from app.schemas import Candidate, Chunk, QueryUnderstanding
from app.services.embeddings import EmbeddingProvider
from app.services.search import SearchHit, SearchIndex, build_filter


def rrf_merge(ranked_lists: Iterable[list[str]], k: int = 60) -> list[tuple[str, float]]:
    """Reciprocal rank fusion: score(d) = Σ 1 / (k + rank_i(d)), rank starting at 1."""
    scores: dict[str, float] = defaultdict(float)
    first_seen: dict[str, int] = {}
    order = 0
    for lst in ranked_lists:
        seen_in_list: set[str] = set()
        for rank, doc_id in enumerate(lst, start=1):
            if doc_id in seen_in_list:
                continue
            seen_in_list.add(doc_id)
            scores[doc_id] += 1.0 / (k + rank)
            if doc_id not in first_seen:
                first_seen[doc_id] = order
                order += 1
    return sorted(scores.items(), key=lambda kv: (-kv[1], first_seen[kv[0]]))


_VERSION_SUFFIX = re.compile(r"(__\d{4}-\d{2}-\d{2})?(__v\d+(\.\d+)*)?$", re.I)
_DATE_TOKEN = re.compile(
    r"[_\-\s]+(\d{4}[-_]\d{2}[-_]\d{2}|\d{4}-\d{2,4}|v\d+(?:\.\d+)*|rev\d*|revised|final|old|new)(?=$|[_\-\s])", re.I
)


def document_family(chunk: Chunk) -> str:
    """Key shared by all versions of one document, e.g. ``circulars/exam-form-late-fee-circular``."""
    name = chunk.blob_name or chunk.document_name
    name = re.sub(r"\.[A-Za-z0-9]{2,5}$", "", name)  # extension
    name = _VERSION_SUFFIX.sub("", name)
    name = _DATE_TOKEN.sub("", name)
    return name.strip(" _-").lower()


def _version_key(chunk: Chunk) -> tuple[str, tuple[int, ...]]:
    nums = tuple(int(x) for x in re.findall(r"\d+", chunk.version or "0")) or (0,)
    return (chunk.effective_date or "", nums)


def resolve_versions(cands: list[Candidate]) -> tuple[list[Candidate], set[str]]:
    """Drop chunks whose document is superseded by a newer version that was also retrieved."""
    latest: dict[str, tuple[tuple[str, tuple[int, ...]], str]] = {}
    for c in cands:
        fam = document_family(c.chunk)
        key = _version_key(c.chunk)
        if fam not in latest or key > latest[fam][0]:
            latest[fam] = (key, c.chunk.document_id)
    superseded = {c.chunk.document_id for c in cands if latest[document_family(c.chunk)][1] != c.chunk.document_id}
    return [c for c in cands if c.chunk.document_id not in superseded], superseded


async def retrieve(
    qu: QueryUnderstanding,
    original_query: str,
    document_ids: list[str] | None,
    *,
    search: SearchIndex,
    embeddings: EmbeddingProvider,
    settings: Settings,
) -> list[Candidate]:
    texts = [original_query] if original_query.strip() == qu.english_query.strip() else [original_query, qu.english_query]
    vectors = await embeddings.embed(texts)

    use_cat_filter = settings.category_mode == "filter" and qu.intent_category != "other"
    semantic = settings.reranker == "azure_semantic"
    top = settings.retrieval_top_k

    async def run(filt: str | None) -> list[list[SearchHit]]:
        jobs = [search.keyword_search(qu.english_query, filter=filt, top=top, semantic=semantic)]
        jobs += [search.vector_search(v, filter=filt, top=top) for v in vectors]
        return list(await asyncio.gather(*jobs))

    results = await run(build_filter(document_ids, qu.intent_category if use_cat_filter else None))
    if use_cat_filter and not any(results):  # intent guess was wrong -> retry unfiltered
        results = await run(build_filter(document_ids))

    by_id: dict[str, Candidate] = {}
    for list_idx, hits in enumerate(results):
        for h in hits:
            c = by_id.setdefault(h.chunk.id, Candidate(chunk=h.chunk))
            if list_idx == 0:
                c.keyword_score = h.score
                if h.reranker_score is not None:
                    c.reranker_score = max(0.0, min(1.0, float(h.reranker_score) / 4.0))
            else:
                c.vector_score = max(c.vector_score or -1.0, h.score)

    fused = rrf_merge([[h.chunk.id for h in hits] for hits in results], k=settings.rrf_k)[:top]
    cands: list[Candidate] = []
    for cid, s in fused:
        c = by_id[cid]
        c.rrf_score = s
        searchable = f"{c.chunk.section_title or ''} {c.chunk.content}"
        c.coverage = max(term_coverage(qu.english_query, searchable), term_coverage(original_query, searchable))
        cands.append(c)
    cands, _ = resolve_versions(cands)
    return cands
