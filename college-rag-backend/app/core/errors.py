"""Domain errors mapped to friendly HTTP responses (never leak internals)."""
from __future__ import annotations


class AppError(Exception):
    status_code = 500
    public_message = "Internal server error."

    def __init__(self, public_message: str | None = None, *, retry_after: int | None = None):
        super().__init__(public_message or self.public_message)
        if public_message:
            self.public_message = public_message
        self.retry_after = retry_after


class UpstreamError(AppError):
    """An Azure / LLM dependency failed after retries."""

    status_code = 503
    public_message = "An upstream service is temporarily unavailable. Please try again shortly."


class UpstreamRateLimited(UpstreamError):
    status_code = 503
    public_message = "The service is busy right now. Please try again in a minute."


class BudgetExceeded(AppError):
    status_code = 503
    public_message = "The service is busy right now (daily usage limit reached). Please try again later."


class RateLimited(AppError):
    status_code = 429
    public_message = "Too many requests. Please slow down and try again shortly."


class NotFound(AppError):
    status_code = 404
    public_message = "Not found."


class ConfigurationError(AppError):
    status_code = 503
    public_message = "The service is not configured correctly."

