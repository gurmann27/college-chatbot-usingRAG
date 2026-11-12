"""Persistence models (storage-agnostic) and the SQLite schema."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    """ISO-8601 UTC with 'Z' suffix (what the frontend's Date.parse expects)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_dt(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


@dataclass
class MessageRecord:
    id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime
    sources: list[dict[str, Any]] = field(default_factory=list)
    language: str | None = None
    abstained: bool = False


@dataclass
class SessionRecord:
    id: str
    client_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list[MessageRecord] = field(default_factory=list)


SQLITE_SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS sessions (
    client_id   TEXT NOT NULL,
    id          TEXT NOT NULL,
    title       TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    PRIMARY KEY (client_id, id)
);
CREATE INDEX IF NOT EXISTS ix_sessions_updated ON sessions (client_id, updated_at DESC);
CREATE TABLE IF NOT EXISTS messages (
    id          TEXT PRIMARY KEY,
    client_id   TEXT NOT NULL,
    session_id  TEXT NOT NULL,
    role        TEXT NOT NULL,
    content     TEXT NOT NULL,
    sources     TEXT NOT NULL DEFAULT '[]',
    language    TEXT,
    abstained   INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    FOREIGN KEY (client_id, session_id) REFERENCES sessions (client_id, id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_messages_session ON messages (client_id, session_id, created_at);
CREATE TABLE IF NOT EXISTS documents (
    id          TEXT PRIMARY KEY,
    blob_name   TEXT NOT NULL UNIQUE,
    data        TEXT NOT NULL
);
"""

