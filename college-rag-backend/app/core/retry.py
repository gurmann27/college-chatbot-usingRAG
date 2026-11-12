"""Async retry with exponential backoff + jitter for 429/5xx upstream responses."""
from __future__ import annotations

import asyncio
import logging
import random
from typing import Awaitable, Callable, TypeVar

import httpx

from app.core.errors import UpstreamError, UpstreamRateLimited

T = TypeVar("T")
log = logging.getLogger(__name__)

RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}


class RetryableHTTPError(Exception):
    def __init__(self, status: int, retry_after: float | None = None):
        super().__init__(f"upstream status {status}")
        self.status = status
        self.retry_after = retry_after


def raise_for_status(resp: httpx.Response) -> None:
    """Raise RetryableHTTPError for retryable codes, UpstreamError for others."""
    if resp.status_code < 400:
        return
    if resp.status_code in RETRYABLE_STATUS:
        ra = resp.headers.get("retry-after-ms") or resp.headers.get("retry-after")
        retry_after: float | None = None
        if ra:
            try:
                retry_after = float(ra) / (1000 if "retry-after-ms" in resp.headers else 1)
            except ValueError:
                retry_after = None
        raise RetryableHTTPError(resp.status_code, retry_after)
    # 4xx (other than 408/429) are not retryable. Do not include body (may echo input).
    log.warning("upstream_error", extra={"status": resp.status_code, "service": resp.request.url.host})
    raise UpstreamError()


async def with_retry(
    fn: Callable[[], Awaitable[T]],
    *,
    max_retries: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 20.0,
    op: str = "upstream",
) -> T:
    attempt = 0
    while True:
        try:
            return await fn()
        except (RetryableHTTPError, httpx.TransportError, httpx.TimeoutException) as exc:
            attempt += 1
            status = getattr(exc, "status", None)
            if attempt > max_retries:
                log.warning("upstream_retries_exhausted", extra={"op": op, "status": status})
                if status == 429:
                    raise UpstreamRateLimited() from None
                raise UpstreamError() from None
            delay = getattr(exc, "retry_after", None) or min(max_delay, base_delay * 2 ** (attempt - 1))
            delay = delay * (0.8 + random.random() * 0.4)
            log.info("upstream_retry", extra={"op": op, "attempt": attempt, "status": status, "delay_s": round(delay, 2)})
            await asyncio.sleep(delay)

