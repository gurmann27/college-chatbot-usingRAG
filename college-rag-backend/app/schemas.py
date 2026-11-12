"""Public API schemas (frontend contract) and internal pipeline models."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

CATEGORIES = ("admissions", "fees", "exams", "hostel", "scholarships", "circulars", "other")


# ============================================================================ API: chat
class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    session_id: str | None = Field(default=None, max_length=128)
    document_ids: list[str] | None = Field(default=None, max_length=50)

    @field_validator("query")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("query must not be empty")
        return v

    @field_validator("session_id")
    @classmethod
    def _session_id(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        import re

        if not re.fullmatch(r"[A-Za-z0-9_\-:.]{1,128}", v):
            raise ValueError("session_id contains invalid characters")
        return v


class SourceOut(BaseModel):
    id: str
    document_id: str
    document_name: str
    page: int | None = None
    score: float = Field(ge=0.0, le=1.0)
    snippet: str
    validated: bool = False
    category: str | None = None
    effective_date: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    message_id: str
    answer: str
    language: str
    abstained: bool
    sources: list[SourceOut]


# ============================================================================ API: history
class MessageOut(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    sources: list[SourceOut] = []
    created_at: str


class SessionOut(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    messages: list[MessageOut]


# ============================================================================ API: documents
class DocumentOut(BaseModel):
    id: str
    name: str
    size_bytes: int | None = None
    pages: int | None = None
    uploaded_at: str
    status: Literal["indexed", "processing", "failed"]
    category: str | None = None
    effective_date: str | None = None
    version: str | None = None
    language: str | None = None


class ReindexResult(BaseModel):
    status: str
    processed: int = 0
    skipped: int = 0
    failed: int = 0
    deleted: int = 0
    details: list[dict] = []


# ============================================================================ internal
class QueryUnderstanding(BaseModel):
    language: str = "en"  # e.g. en, hi, hi-Latn, ta
    script: str = "Latn"  # ISO 15924
    is_hinglish: bool = False
    english_query: str
    intent_category: str = "other"
    source: Literal["heuristic", "llm", "fallback"] = "heuristic"

    @field_validator("intent_category")
    @classmethod
    def _cat(cls, v: str) -> str:
        v = (v or "other").lower().strip()
        return v if v in CATEGORIES else "other"


class Chunk(BaseModel):
    """A chunk as stored in / returned from the search index."""

    id: str
    document_id: str
    document_name: str
    page: int | None = None
    content: str
    section_title: str | None = None
    category: str | None = None
    effective_date: str | None = None
    version: str | None = None
    language: str | None = None
    content_hash: str | None = None
    blob_name: str | None = None


class Candidate(BaseModel):
    """A retrieval candidate with all the scores collected along the pipeline."""

    chunk: Chunk
    rrf_score: float = 0.0
    keyword_score: float | None = None  # raw BM25
    vector_score: float | None = None  # cosine similarity (best of both query vectors)
    reranker_score: float | None = None  # already normalised 0..1 when set
    coverage: float = 0.0
    score: float = 0.0  # final normalised 0..1


class DocumentRecord(BaseModel):
    id: str
    blob_name: str
    name: str
    size_bytes: int | None = None
    pages: int | None = None
    uploaded_at: datetime
    status: Literal["indexed", "processing", "failed", "superseded", "deleted"] = "processing"
    category: str | None = None
    effective_date: str | None = None
    version: str | None = None
    language: str | None = None
    content_hash: str | None = None
    chunk_count: int = 0
    error: str | None = None

