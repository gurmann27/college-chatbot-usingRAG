"""In-memory search index implementing BM25, cosine vector search and OData filters."""
from __future__ import annotations

import math
import re
from collections import Counter

from app.core.text import content_terms, expand_synonyms
from app.schemas import Chunk
from app.services.search import SearchHit, SearchIndex

_SEARCH_IN = re.compile(r"search\.in\(\s*document_id\s*,\s*'([^']*)'\s*,\s*','\s*\)")
_CAT_EQ = re.compile(r"category\s+eq\s+'([^']*)'")


def _parse_filter(filt: str | None) -> tuple[set[str] | None, str | None]:
    if not filt:
        return None, None
    doc_ids = None
    m = _SEARCH_IN.search(filt)
    if m:
        doc_ids = {s.strip() for s in m.group(1).split(",") if s.strip()}
    m2 = _CAT_EQ.search(filt)
    cat = m2.group(1) if m2 else None
    return doc_ids, cat


class InMemorySearchIndex(SearchIndex):
    def __init__(self) -> None:
        self._docs: dict[str, tuple[Chunk, list[float], Counter[str]]] = {}

    def _allowed(self, chunk: Chunk, filt: str | None) -> bool:
        doc_ids, cat = _parse_filter(filt)
        if doc_ids is not None and chunk.document_id not in doc_ids:
            return False
        if cat is not None and chunk.category != cat:
            return False
        return True

    async def upsert(self, docs: list[dict]) -> None:
        for d in docs:
            ch = Chunk(**{k: d.get(k) for k in Chunk.model_fields if k in d})
            vec = list(d.get("content_vector") or [])
            base_terms = content_terms(f"{ch.document_name} {ch.section_title or ''} {ch.content}")
            bag = Counter(base_terms)
            for syn in expand_synonyms(base_terms):
                if syn not in bag:
                    bag[syn] = 1
            self._docs[ch.id] = (ch, vec, bag)

    async def delete_document(self, document_id: str) -> int:
        ids = [cid for cid, (ch, _, _) in self._docs.items() if ch.document_id == document_id]
        for cid in ids:
            del self._docs[cid]
        return len(ids)

    async def keyword_search(self, text: str, *, filter: str | None, top: int, semantic: bool = False) -> list[SearchHit]:
        q_terms = content_terms(text)
        if not q_terms or not self._docs:
            return []
        pool = [(ch, bag) for ch, _, bag in self._docs.values() if self._allowed(ch, filter)]
        if not pool:
            return []
        n_docs = len(pool)
        avgdl = sum(sum(b.values()) for _, b in pool) / n_docs or 1.0
        df = {t: sum(1 for _, b in pool if t in b) for t in q_terms}
        k1, b = 1.5, 0.75
        hits: list[SearchHit] = []
        for ch, bag in pool:
            dl = sum(bag.values()) or 1
            score = 0.0
            for t in q_terms:
                tf = bag.get(t, 0)
                if not tf:
                    continue
                idf = math.log(1.0 + (n_docs - df[t] + 0.5) / (df[t] + 0.5))
                score += idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * dl / avgdl))
            if score > 0:
                sem = min(4.0, score) if semantic else None
                hits.append(SearchHit(ch, score, sem))
        hits.sort(key=lambda h: -h.score)
        return hits[:top]

    async def vector_search(self, vector: list[float], *, filter: str | None, top: int) -> list[SearchHit]:
        hits: list[SearchHit] = []
        for ch, vec, _ in self._docs.values():
            if not vec or not self._allowed(ch, filter):
                continue
            cos = sum(a * b for a, b in zip(vector, vec))
            if cos > 0:
                hits.append(SearchHit(ch, cos))
        hits.sort(key=lambda h: -h.score)
        return hits[:top]

