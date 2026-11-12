"""Deterministic cross-lingual feature-hashing embeddings for ``MOCK_AZURE=true``.

Every token is first mapped to its English equivalent through the domain lexicon, then
stemmed and hashed into a fixed-dimension L2-normalised vector. Consequently a Hindi
question (``हॉस्टल के नियम``) and an English passage (``hostel rules``) land in the same
subspace and have high cosine similarity, exercising the real vector-search and RRF code.
"""
from __future__ import annotations

import hashlib
import math

from app.core.lexicon import translate_tokens
from app.core.text import EN_STOPWORDS, count_tokens, expand_synonyms, stem, tokenize
from app.core.usage import UsageRecord, record_usage
from app.services.embeddings import EmbeddingProvider


class MockEmbeddings(EmbeddingProvider):
    model = "mock-multilingual-embed"

    def __init__(self, dimensions: int = 256):
        self.dimensions = dimensions

    def _vec(self, text: str) -> list[float]:
        v = [0.0] * self.dimensions
        raw = tokenize(text)
        mapped = translate_tokens(raw)
        terms: list[str] = []
        for tok in mapped:
            for sub in tok.split():
                if sub not in EN_STOPWORDS and len(sub) >= 2:
                    terms.append(stem(sub))
        if not terms:
            terms = [stem(t) for t in raw[:5]] or ["empty"]
        # unigrams + bigrams + synonym expansion for semantic sensitivity
        feats: list[tuple[str, float]] = [(t, 1.0) for t in terms] + [
            (f"{a}_{b}", 1.0) for a, b in zip(terms, terms[1:])
        ]
        for syn in expand_synonyms(terms) - set(terms):
            feats.append((syn, 0.5))
        for f, w in feats:
            h = int.from_bytes(hashlib.md5(f.encode("utf-8")).digest()[:8], "big")
            idx = h % self.dimensions
            sign = 1.0 if (h >> 63) == 0 else -1.0
            v[idx] += sign * w
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        return [round(x / norm, 6) for x in v]

    async def embed(self, texts: list[str]) -> list[list[float]]:
        record_usage(UsageRecord("embedding", self.model, sum(count_tokens(t) for t in texts), 0))
        return [self._vec(t) for t in texts]

