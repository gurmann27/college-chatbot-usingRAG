"""Cache layer (step b).

``CacheBackend`` is a minimal async, string-valued, TTL key/value interface that maps
1:1 onto Redis (GET / SET EX / INCR / DEL), so the in-memory implementation can be
swapped for Azure Cache for Redis without touching the pipeline.

The answer cache stores the *English-level* result (ranked chunks + answers keyed by
language). A hit in another language only needs a cheap re-render call, not retrieval.
The key includes a knowledge-base generation counter that ingestion bumps, so stale
answers are never served after documents change.
"""
from __future__ import annotations

import abc
import asyncio
import json
import time
from collections import OrderedDict
from typing import Any

from app.core.text import normalize_query, sha256

KB_GENERATION_KEY = "kb:generation"


class CacheBackend(abc.ABC):
    @abc.abstractmethod
    async def get(self, key: str) -> str | None: ...

    @abc.abstractmethod
    async def set(self, key: str, value: str, ttl_seconds: int) -> None: ...

    @abc.abstractmethod
    async def delete(self, key: str) -> None: ...

    @abc.abstractmethod
    async def incr(self, key: str) -> int: ...

    async def aclose(self) -> None:  # pragma: no cover
        return None


class InMemoryTTLCache(CacheBackend):
    """LRU + TTL cache. Bounded so it can never exhaust a small container's memory."""

    def __init__(self, max_items: int = 5000, clock=time.monotonic):
        self._data: OrderedDict[str, tuple[float | None, str]] = OrderedDict()
        self._max = max_items
        self._clock = clock
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> str | None:
        async with self._lock:
            item = self._data.get(key)
            if item is None:
                return None
            exp, val = item
            if exp is not None and exp <= self._clock():
                del self._data[key]
                return None
            self._data.move_to_end(key)
            return val

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        async with self._lock:
            exp = self._clock() + ttl_seconds if ttl_seconds > 0 else None
            self._data[key] = (exp, value)
            self._data.move_to_end(key)
            while len(self._data) > self._max:
                self._data.popitem(last=False)

    async def delete(self, key: str) -> None:
        async with self._lock:
            self._data.pop(key, None)

    async def incr(self, key: str) -> int:
        async with self._lock:
            exp, val = self._data.get(key, (None, "0"))
            n = int(val) + 1
            self._data[key] = (exp, str(n))
            return n

    def __len__(self) -> int:
        return len(self._data)


class RedisCache(CacheBackend):  # pragma: no cover - requires a Redis server
    def __init__(self, url: str):
        import redis.asyncio as redis  # lazy import (optional dependency)

        self._r = redis.from_url(url, decode_responses=True)

    async def get(self, key: str) -> str | None:
        return await self._r.get(key)

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        await self._r.set(key, value, ex=ttl_seconds if ttl_seconds > 0 else None)

    async def delete(self, key: str) -> None:
        await self._r.delete(key)

    async def incr(self, key: str) -> int:
        return int(await self._r.incr(key))

    async def aclose(self) -> None:
        await self._r.aclose()


# ----------------------------------------------------------------------------- answer cache
def make_cache_key(english_query: str, document_ids: list[str] | None, generation: str = "0") -> str:
    ids = ",".join(sorted(set(document_ids or [])))
    return f"ans:{generation}:{sha256(normalize_query(english_query) + '|' + ids)[:40]}"


class AnswerCache:
    def __init__(self, backend: CacheBackend, ttl_seconds: int):
        self.backend = backend
        self.ttl = ttl_seconds

    async def generation(self) -> str:
        return await self.backend.get(KB_GENERATION_KEY) or "0"

    async def bump_generation(self) -> int:
        """Invalidate every cached answer (called by ingestion after index changes)."""
        return await self.backend.incr(KB_GENERATION_KEY)

    async def key(self, english_query: str, document_ids: list[str] | None) -> str:
        return make_cache_key(english_query, document_ids, await self.generation())

    async def get(self, key: str) -> dict[str, Any] | None:
        raw = await self.backend.get(key)
        return json.loads(raw) if raw else None

    async def put(self, key: str, entry: dict[str, Any]) -> None:
        await self.backend.set(key, json.dumps(entry, ensure_ascii=False), self.ttl)


def build_cache(backend: str, *, redis_url: str = "", max_items: int = 5000) -> CacheBackend:
    if backend == "redis" and redis_url:
        return RedisCache(redis_url)
    return InMemoryTTLCache(max_items=max_items)

