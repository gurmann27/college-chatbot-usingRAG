"""Structured JSON logging with a per-request id and stage timings.

Rules: never log document text, prompts, answers, keys or PII. Only ids, counts,
latencies, token usage and cost estimates.
"""
from __future__ import annotations

import contextvars
import json
import logging
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")

_RESERVED = set(vars(logging.makeLogRecord({})).keys()) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        for k, v in record.__dict__.items():
            if k not in _RESERVED and not k.startswith("_"):
                payload[k] = v
        if record.exc_info:
            # Exception type only; stack traces stay out of client responses, but are
            # useful for operators, so include them in logs (no secrets in our frames).
            payload["exc_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    # Quiet noisy libraries (they may log URLs containing resource names).
    for noisy in ("httpx", "httpcore", "azure", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


class StageTimer:
    """Collects latency per pipeline stage (milliseconds)."""

    def __init__(self) -> None:
        self.stages: dict[str, float] = {}
        self._t0 = time.perf_counter()

    @contextmanager
    def stage(self, name: str):
        t = time.perf_counter()
        try:
            yield
        finally:
            self.stages[name] = round(self.stages.get(name, 0.0) + (time.perf_counter() - t) * 1000, 2)

    @property
    def total_ms(self) -> float:
        return round((time.perf_counter() - self._t0) * 1000, 2)

