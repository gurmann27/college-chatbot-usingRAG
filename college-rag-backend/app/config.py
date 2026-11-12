"""Application settings (12-factor, environment driven).

Every knob that affects cost, quality or security lives here so it can be tuned per
environment without code changes. Values are read from environment variables (or a
local ``.env`` file) by pydantic-settings.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = str(Path(__file__).resolve().parents[1] / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    # ------------------------------------------------------------------ general
    app_name: str = "college-rag-backend"
    environment: Literal["local", "dev", "prod", "test"] = "local"
    log_level: str = "INFO"
    mock_azure: bool = Field(default=False, description="Use in-memory fakes + sample corpus")
    allowed_origins: str = "http://localhost:5173"

    # ------------------------------------------------------------------ Azure OpenAI
    azure_openai_endpoint: str = ""
    azure_openai_api_key: SecretStr = SecretStr("")
    azure_openai_api_version: str = "2024-10-21"
    # Deployment names: separate models per task (cost control)
    query_model: str = "gpt-4o-mini"
    generation_model: str = "gpt-4o-mini"
    judge_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    embedding_batch_size: int = 64
    llm_provider: Literal["azure_openai", "mock"] = "azure_openai"
    embedding_provider: Literal["azure_openai", "mock"] = "azure_openai"

    # ------------------------------------------------------------------ Azure AI Search
    azure_search_endpoint: str = ""
    azure_search_api_key: SecretStr = SecretStr("")
    azure_search_index: str = "college-docs-index"
    azure_search_api_version: str = "2024-07-01"
    semantic_config_name: str = "default-semantic"

    # ------------------------------------------------------------------ Blob storage
    azure_storage_connection_string: SecretStr = SecretStr("")
    azure_storage_account_url: str = ""  # used with managed identity when no connection string
    blob_container: str = "college-docs"

    # ------------------------------------------------------------------ OCR (optional)
    ocr_enabled: bool = False
    document_intelligence_endpoint: str = ""
    document_intelligence_api_key: SecretStr = SecretStr("")

    # ------------------------------------------------------------------ persistence
    session_store: Literal["sqlite", "cosmos"] = "sqlite"
    sqlite_path: str = "./data/rag.db"
    cosmos_endpoint: str = ""
    cosmos_key: SecretStr = SecretStr("")
    cosmos_database: str = "collegerag"
    cosmos_sessions_container: str = "sessions"
    cosmos_documents_container: str = "documents"
    retention_days: int = 90

    # ------------------------------------------------------------------ cache
    cache_backend: Literal["memory", "redis"] = "memory"
    redis_url: str = ""
    cache_ttl_seconds: int = 24 * 3600
    embedding_cache_ttl_seconds: int = 7 * 24 * 3600
    cache_max_items: int = 5000

    # ------------------------------------------------------------------ retrieval
    retrieval_top_k: int = Field(default=20, ge=1, le=50)
    rerank_top_k: int = Field(default=5, ge=1, le=10)
    rrf_k: int = 60
    reranker: Literal["none", "azure_semantic", "llm"] = "none"
    relevance_threshold: float = Field(default=0.28, ge=0.0, le=1.0)
    category_mode: Literal["boost", "filter", "off"] = "boost"
    category_boost: float = 0.05
    # Calibration of cosine similarity into 0..1 (text-embedding-3-small)
    vector_score_floor: float = 0.15
    vector_score_ceil: float = 0.55
    keyword_weight: float = 0.6  # weight of query-term coverage in the heuristic score
    vector_weight: float = 0.4

    # ------------------------------------------------------------------ generation / verification
    max_context_tokens: int = 3000
    max_output_tokens: int = 500
    generation_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    query_max_output_tokens: int = 200
    faithfulness_check: bool = False
    regenerate_on_unsupported_fact: bool = True
    max_query_chars: int = 1000

    # ------------------------------------------------------------------ cost controls
    rate_limit_per_minute: int = 300
    global_rate_limit_per_minute: int = 1000
    daily_token_budget: int = 2_000_000
    # USD per 1K tokens (input, output) used only for cost logging
    price_query_in: float = 0.00015
    price_query_out: float = 0.0006
    price_generation_in: float = 0.00015
    price_generation_out: float = 0.0006
    price_judge_in: float = 0.00015
    price_judge_out: float = 0.0006
    price_embedding: float = 0.00002

    # ------------------------------------------------------------------ timeouts / retries
    chat_timeout_seconds: float = 55.0
    upstream_timeout_seconds: float = 30.0
    upstream_max_retries: int = 3

    # ------------------------------------------------------------------ admin auth
    admin_auth_mode: Literal["api_key", "entra"] = "api_key"
    admin_api_key: SecretStr = SecretStr("")
    entra_tenant_id: str = ""
    entra_audience: str = ""
    entra_admin_role: str = "RAG.Admin"

    # Salt used to derive an anonymous client id from IP + user agent when the
    # X-Client-Id header is missing. Never logged.
    client_id_salt: SecretStr = SecretStr("change-me")

    @field_validator("allowed_origins")
    @classmethod
    def _no_wildcard(cls, v: str) -> str:
        if "*" in v:
            raise ValueError("Wildcard CORS origins are not allowed")
        return v

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    def apply_mock_defaults(self) -> "Settings":
        """In MOCK_AZURE mode force every provider to its in-memory fake."""
        if self.mock_azure:
            self.llm_provider = "mock"
            self.embedding_provider = "mock"
            self.embedding_dimensions = 256
            if self.reranker == "azure_semantic":
                self.reranker = "none"
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings().apply_mock_defaults()

