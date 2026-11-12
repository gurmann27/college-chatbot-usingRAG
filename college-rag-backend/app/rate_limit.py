"""Per-client + global sliding-window rate limiter (step cost control)."""
from __future__ import annotations

import asyncio
import math
import time
from collections import deque
from collections.abc import Callable

from fastapi import Depends, Request

from app.auth import resolve_client_id
from app.core.errors import RateLimited


class SlidingWindowLimiter:
    def __init__(
        self,
        per_client_per_minute: int,
        global_per_minute: int,
        *,
        window: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.per_client = per_client_per_minute
        self.global_limit = global_per_minute
        self.window = window
        self._clock = clock
        self._clients: dict[str, deque[float]] = {}
        self._global: deque[float] = deque()
        self._lock = asyncio.Lock()

    def _prune(self, q: deque[float], cutoff: float) -> None:
        while q and q[0] <= cutoff:
            q.popleft()

    async def check(self, client_id: str) -> None:
        now = self._clock()
        cutoff = now - self.window
        async with self._lock:
            self._prune(self._global, cutoff)
            if self.global_limit > 0 and len(self._global) >= self.global_limit:
                retry = max(1, math.ceil(self._global[0] + self.window - now))
                raise RateLimited(retry_after=retry)
            q = self._clients.get(client_id)
            if q is None:
                q = deque()
                self._clients[client_id] = q
            self._prune(q, cutoff)
            if self.per_client > 0 and len(q) >= self.per_client:
                retry = max(1, math.ceil(q[0] + self.window - now))
                raise RateLimited(retry_after=retry)
            q.append(now)
            self._global.append(now)
            # Opportunistic cleanup so idle client keys do not accumulate forever.
            if len(self._clients) > 10_000:
                dead = [k for k, v in self._clients.items() if not v or v[-1] <= cutoff]
                for k in dead:
                    del self._clients[k]


async def enforce_rate_limit(
    request: Request,
    client_id: str = Depends(resolve_client_id),
) -> str:
    limiter: SlidingWindowLimiter = request.app.state.rate_limiter
    await limiter.check(client_id)
    return client_id

