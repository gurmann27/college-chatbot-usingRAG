"""Token usage tracking (per request) and a daily token budget."""
from __future__ import annotations

import asyncio
import contextvars
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.config import Settings


@dataclass
class UsageRecord:
    task: str  # query_understanding | generation | judge | rerank | translate | embedding
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass
class RequestUsage:
    records: list[UsageRecord] = field(default_factory=list)

    def add(self, rec: UsageRecord) -> None:
        self.records.append(rec)

    @property
    def total_tokens(self) -> int:
        return sum(r.prompt_tokens + r.completion_tokens for r in self.records)

    def llm_calls(self, task: str | None = None) -> int:
        return sum(1 for r in self.records if r.task != "embedding" and (task is None or r.task == task))

    def estimated_cost_usd(self, s: Settings) -> float:
        prices = {
            "query_understanding": (s.price_query_in, s.price_query_out),
            "generation": (s.price_generation_in, s.price_generation_out),
            "translate": (s.price_generation_in, s.price_generation_out),
            "judge": (s.price_judge_in, s.price_judge_out),
            "rerank": (s.price_judge_in, s.price_judge_out),
            "embedding": (s.price_embedding, 0.0),
        }
        cost = 0.0
        for r in self.records:
            pin, pout = prices.get(r.task, (s.price_generation_in, s.price_generation_out))
            cost += r.prompt_tokens / 1000 * pin + r.completion_tokens / 1000 * pout
        return round(cost, 6)

    def summary(self) -> dict:
        by_task: dict[str, int] = {}
        for r in self.records:
            by_task[r.task] = by_task.get(r.task, 0) + r.prompt_tokens + r.completion_tokens
        return {"total_tokens": self.total_tokens, "tokens_by_task": by_task, "llm_calls": self.llm_calls()}


_usage_var: contextvars.ContextVar[RequestUsage | None] = contextvars.ContextVar("usage", default=None)


def start_request_usage() -> RequestUsage:
    u = RequestUsage()
    _usage_var.set(u)
    return u


def current_usage() -> RequestUsage | None:
    return _usage_var.get()


class TokenBudget:
    """Global daily token budget (UTC day). In-process; swap for Redis INCR for multi-replica."""

    def __init__(self, daily_limit: int):
        self.daily_limit = daily_limit
        self._day = self._today()
        self._used = 0
        self._lock = asyncio.Lock()

    @staticmethod
    def _today() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _roll(self) -> None:
        today = self._today()
        if today != self._day:
            self._day, self._used = today, 0

    def exhausted(self) -> bool:
        self._roll()
        return self.daily_limit > 0 and self._used >= self.daily_limit

    async def consume(self, tokens: int) -> None:
        async with self._lock:
            self._roll()
            self._used += max(0, tokens)

    @property
    def used(self) -> int:
        self._roll()
        return self._used


_budget_var: contextvars.ContextVar[TokenBudget | None] = contextvars.ContextVar("budget", default=None)


def record_usage(rec: UsageRecord, budget: TokenBudget | None = None) -> None:
    """Called by providers after every upstream call."""
    u = _usage_var.get()
    if u is not None:
        u.add(rec)
    b = budget or _budget_var.get()
    if b is not None:
        b._roll()
        b._used += rec.prompt_tokens + rec.completion_tokens


def bind_budget(budget: TokenBudget) -> None:
    _budget_var.set(budget)

