"""LLM provider interface + Azure OpenAI implementation.

Pipeline code depends only on :class:`LLMProvider`. To add a provider (e.g. Gemini,
Anthropic, a local model) implement ``complete`` and register it in ``build_llm``.
"""
from __future__ import annotations

import abc
import logging
from dataclasses import dataclass
from typing import Literal

import httpx

from app.config import Settings
from app.core.errors import ConfigurationError
from app.core.retry import raise_for_status, with_retry
from app.core.usage import TokenBudget, UsageRecord, record_usage

log = logging.getLogger(__name__)

Task = Literal["query_understanding", "generation", "translate", "judge", "rerank"]


@dataclass
class ChatMessage:
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass
class LLMResult:
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""


class LLMProvider(abc.ABC):
    def __init__(self, budget: TokenBudget | None = None):
        self.budget = budget

    @abc.abstractmethod
    async def _complete(
        self,
        messages: list[ChatMessage],
        *,
        model: str,
        temperature: float,
        max_tokens: int,
        json_mode: bool,
        task: Task,
    ) -> LLMResult: ...

    async def complete(
        self,
        messages: list[ChatMessage],
        *,
        model: str,
        task: Task,
        temperature: float = 0.0,
        max_tokens: int = 500,
        json_mode: bool = False,
    ) -> LLMResult:
        res = await self._complete(
            messages, model=model, temperature=temperature, max_tokens=max_tokens, json_mode=json_mode, task=task
        )
        record_usage(UsageRecord(task, model, res.prompt_tokens, res.completion_tokens), self.budget)
        return res

    async def aclose(self) -> None:  # pragma: no cover - trivial
        return None


class AzureOpenAIProvider(LLMProvider):
    """Calls the Azure OpenAI chat completions REST API (deployment name == model setting)."""

    def __init__(self, settings: Settings, budget: TokenBudget | None = None):
        super().__init__(budget)
        if not settings.azure_openai_endpoint or not settings.azure_openai_api_key.get_secret_value():
            raise ConfigurationError("Azure OpenAI is not configured.")
        self.s = settings
        self._client = httpx.AsyncClient(
            base_url=settings.azure_openai_endpoint.rstrip("/"),
            headers={"api-key": settings.azure_openai_api_key.get_secret_value()},
            timeout=settings.upstream_timeout_seconds,
        )

    async def _complete(self, messages, *, model, temperature, max_tokens, json_mode, task) -> LLMResult:
        body: dict = {
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        url = f"/openai/deployments/{model}/chat/completions?api-version={self.s.azure_openai_api_version}"

        async def call() -> dict:
            resp = await self._client.post(url, json=body)
            raise_for_status(resp)
            return resp.json()

        data = await with_retry(call, max_retries=self.s.upstream_max_retries, op=f"llm:{task}")
        choice = (data.get("choices") or [{}])[0]
        # Azure content filter -> treat as empty output (pipeline will abstain)
        text = (choice.get("message") or {}).get("content") or ""
        usage = data.get("usage") or {}
        return LLMResult(text, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0), model)

    async def aclose(self) -> None:
        await self._client.aclose()


def build_llm(settings: Settings, budget: TokenBudget | None = None) -> LLMProvider:
    if settings.llm_provider == "mock" or settings.mock_azure:
        from app.services.mock.llm import MockLLMProvider

        return MockLLMProvider(budget)
    if settings.llm_provider == "azure_openai":
        return AzureOpenAIProvider(settings, budget)
    raise ConfigurationError(f"Unknown LLM provider {settings.llm_provider}")

