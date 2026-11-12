"""Repository interfaces with SQLite (local dev) and Azure Cosmos DB (serverless) backends.

Sessions are partitioned by the anonymous client id: (client_id, session_id) is the
key, so one client can never read, append to or delete another client's session.
"""
from __future__ import annotations

import abc
import asyncio
import json
import os
import sqlite3
import threading
from datetime import timedelta

from app.config import Settings
from app.db.models import SQLITE_SCHEMA, MessageRecord, SessionRecord, iso, parse_dt, utcnow
from app.schemas import DocumentRecord


# ============================================================================ interfaces
class SessionRepository(abc.ABC):
    @abc.abstractmethod
    async def get_session(self, client_id: str, session_id: str) -> SessionRecord | None: ...

    @abc.abstractmethod
    async def append_messages(
        self, client_id: str, session_id: str, title: str, messages: list[MessageRecord]
    ) -> SessionRecord:
        """Create the session if needed (title only set on creation) and append messages."""

    @abc.abstractmethod
    async def list_sessions(self, client_id: str, limit: int = 100) -> list[SessionRecord]:
        """Sessions with messages, newest (updated_at) first."""

    @abc.abstractmethod
    async def delete_session(self, client_id: str, session_id: str) -> bool: ...

    @abc.abstractmethod
    async def purge_expired(self, retention_days: int) -> int: ...

    async def aclose(self) -> None:  # pragma: no cover
        return None


class DocumentRegistry(abc.ABC):
    """Ingestion state per blob: fingerprint, status, page count... Drives GET /documents."""

    @abc.abstractmethod
    async def get(self, document_id: str) -> DocumentRecord | None: ...

    @abc.abstractmethod
    async def upsert(self, record: DocumentRecord) -> None: ...

    @abc.abstractmethod
    async def list(self) -> list[DocumentRecord]: ...

    @abc.abstractmethod
    async def delete(self, document_id: str) -> None: ...


# ============================================================================ SQLite
class SQLiteStore(SessionRepository, DocumentRegistry):
    """Single-file SQLite store. Calls run in a worker thread to keep the event loop free."""

    def __init__(self, path: str):
        if path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(SQLITE_SCHEMA)
        self._lock = threading.Lock()

    async def _run(self, fn, *args):
        def wrapped():
            with self._lock:
                try:
                    res = fn(self._conn, *args)
                    self._conn.commit()
                    return res
                except Exception:
                    self._conn.rollback()
                    raise

        return await asyncio.to_thread(wrapped)

    # ------------------------------------------------------------------ sessions
    @staticmethod
    def _load_messages(conn, client_id: str, session_id: str) -> list[MessageRecord]:
        rows = conn.execute(
            "SELECT * FROM messages WHERE client_id=? AND session_id=? ORDER BY created_at, rowid",
            (client_id, session_id),
        ).fetchall()
        return [
            MessageRecord(
                id=r["id"],
                role="user" if r["role"] == "user" else "assistant",
                content=r["content"],
                created_at=parse_dt(r["created_at"]),
                sources=json.loads(r["sources"]),
                language=r["language"],
                abstained=bool(r["abstained"]),
            )
            for r in rows
        ]

    @classmethod
    def _row_to_session(cls, conn, r) -> SessionRecord:
        return SessionRecord(
            id=r["id"], client_id=r["client_id"], title=r["title"],
            created_at=parse_dt(r["created_at"]), updated_at=parse_dt(r["updated_at"]),
            messages=cls._load_messages(conn, r["client_id"], r["id"]),
        )

    async def get_session(self, client_id, session_id):
        def q(conn):
            r = conn.execute("SELECT * FROM sessions WHERE client_id=? AND id=?", (client_id, session_id)).fetchone()
            return self._row_to_session(conn, r) if r else None

        return await self._run(q)

    async def append_messages(self, client_id, session_id, title, messages):
        def q(conn):
            now = iso(utcnow())
            conn.execute(
                "INSERT INTO sessions (client_id, id, title, created_at, updated_at) VALUES (?,?,?,?,?) "
                "ON CONFLICT(client_id, id) DO UPDATE SET updated_at=excluded.updated_at",
                (client_id, session_id, title, now, now),
            )
            conn.executemany(
                "INSERT INTO messages (id, client_id, session_id, role, content, sources, language, abstained, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                [
                    (m.id, client_id, session_id, m.role, m.content, json.dumps(m.sources, ensure_ascii=False),
                     m.language, int(m.abstained), iso(m.created_at))
                    for m in messages
                ],
            )
            r = conn.execute("SELECT * FROM sessions WHERE client_id=? AND id=?", (client_id, session_id)).fetchone()
            return self._row_to_session(conn, r)

        return await self._run(q)

    async def list_sessions(self, client_id, limit=100):
        def q(conn):
            rows = conn.execute(
                "SELECT * FROM sessions WHERE client_id=? ORDER BY updated_at DESC LIMIT ?", (client_id, limit)
            ).fetchall()
            return [self._row_to_session(conn, r) for r in rows]

        return await self._run(q)

    async def delete_session(self, client_id, session_id):
        def q(conn):
            conn.execute("DELETE FROM messages WHERE client_id=? AND session_id=?", (client_id, session_id))
            cur = conn.execute("DELETE FROM sessions WHERE client_id=? AND id=?", (client_id, session_id))
            return cur.rowcount > 0

        return await self._run(q)

    async def purge_expired(self, retention_days):
        cutoff = iso(utcnow() - timedelta(days=retention_days))

        def q(conn):
            old = conn.execute("SELECT client_id, id FROM sessions WHERE updated_at < ?", (cutoff,)).fetchall()
            for r in old:
                conn.execute("DELETE FROM messages WHERE client_id=? AND session_id=?", (r["client_id"], r["id"]))
            conn.execute("DELETE FROM sessions WHERE updated_at < ?", (cutoff,))
            return len(old)

        return await self._run(q)

    # ------------------------------------------------------------------ documents
    async def get(self, document_id):
        def q(conn):
            r = conn.execute("SELECT data FROM documents WHERE id=?", (document_id,)).fetchone()
            return DocumentRecord.model_validate_json(r["data"]) if r else None

        return await self._run(q)

    async def upsert(self, record):
        def q(conn):
            conn.execute(
                "INSERT INTO documents (id, blob_name, data) VALUES (?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET blob_name=excluded.blob_name, data=excluded.data",
                (record.id, record.blob_name, record.model_dump_json()),
            )

        await self._run(q)

    async def list(self):
        def q(conn):
            return [DocumentRecord.model_validate_json(r["data"]) for r in conn.execute("SELECT data FROM documents")]

        return await self._run(q)

    async def delete(self, document_id):
        await self._run(lambda conn: conn.execute("DELETE FROM documents WHERE id=?", (document_id,)))

    async def aclose(self) -> None:
        await asyncio.to_thread(self._conn.close)


# ============================================================================ Cosmos DB
class CosmosStore(SessionRepository, DocumentRegistry):  # pragma: no cover - requires Azure
    """Azure Cosmos DB (serverless). One item per session (messages embedded),
    partition key /client_id; container default TTL enforces retention automatically."""

    def __init__(self, settings: Settings):
        from azure.cosmos.aio import CosmosClient

        key = settings.cosmos_key.get_secret_value()
        if key:
            self._client = CosmosClient(settings.cosmos_endpoint, credential=key)
        else:
            from azure.identity.aio import DefaultAzureCredential

            self._client = CosmosClient(settings.cosmos_endpoint, credential=DefaultAzureCredential())
        self.s = settings
        self._ready = False

    async def _init(self):
        if self._ready:
            return
        from azure.cosmos import PartitionKey

        db = await self._client.create_database_if_not_exists(self.s.cosmos_database)
        self._sessions = await db.create_container_if_not_exists(
            id=self.s.cosmos_sessions_container,
            partition_key=PartitionKey(path="/client_id"),
            default_ttl=self.s.retention_days * 86400,
        )
        self._docs = await db.create_container_if_not_exists(
            id=self.s.cosmos_documents_container, partition_key=PartitionKey(path="/id")
        )
        self._ready = True

    @staticmethod
    def _to_session(item: dict) -> SessionRecord:
        return SessionRecord(
            id=item["id"], client_id=item["client_id"], title=item["title"],
            created_at=parse_dt(item["created_at"]), updated_at=parse_dt(item["updated_at"]),
            messages=[
                MessageRecord(
                    id=m["id"],
                    role="user" if m["role"] == "user" else "assistant",
                    content=m["content"],
                    created_at=parse_dt(m["created_at"]),
                    sources=m.get("sources", []),
                    language=m.get("language"),
                    abstained=m.get("abstained", False),
                )
                for m in item.get("messages", [])
            ],
        )

    async def get_session(self, client_id, session_id):
        from azure.cosmos.exceptions import CosmosResourceNotFoundError

        await self._init()
        try:
            item = await self._sessions.read_item(session_id, partition_key=client_id)
        except CosmosResourceNotFoundError:
            return None
        return self._to_session(item)

    async def append_messages(self, client_id, session_id, title, messages):
        from azure.cosmos.exceptions import CosmosResourceNotFoundError

        await self._init()
        now = iso(utcnow())
        try:
            item = await self._sessions.read_item(session_id, partition_key=client_id)
        except CosmosResourceNotFoundError:
            item = {"id": session_id, "client_id": client_id, "title": title, "created_at": now, "messages": []}
        item["updated_at"] = now
        item["messages"].extend(
            {"id": m.id, "role": m.role, "content": m.content, "created_at": iso(m.created_at),
             "sources": m.sources, "language": m.language, "abstained": m.abstained}
            for m in messages
        )
        item["ttl"] = self.s.retention_days * 86400
        await self._sessions.upsert_item(item)
        return self._to_session(item)

    async def list_sessions(self, client_id, limit=100):
        await self._init()
        q = "SELECT TOP @n * FROM c WHERE c.client_id = @cid ORDER BY c.updated_at DESC"
        items = self._sessions.query_items(
            q, parameters=[{"name": "@n", "value": limit}, {"name": "@cid", "value": client_id}],
            partition_key=client_id,
        )
        return [self._to_session(i) async for i in items]

    async def delete_session(self, client_id, session_id):
        from azure.cosmos.exceptions import CosmosResourceNotFoundError

        await self._init()
        try:
            await self._sessions.delete_item(session_id, partition_key=client_id)
            return True
        except CosmosResourceNotFoundError:
            return False

    async def purge_expired(self, retention_days):
        return 0  # handled by container TTL

    async def get(self, document_id):
        from azure.cosmos.exceptions import CosmosResourceNotFoundError

        await self._init()
        try:
            item = await self._docs.read_item(document_id, partition_key=document_id)
        except CosmosResourceNotFoundError:
            return None
        return DocumentRecord.model_validate(item)

    async def upsert(self, record):
        await self._init()
        await self._docs.upsert_item(json.loads(record.model_dump_json()))

    async def list(self):
        await self._init()
        return [DocumentRecord.model_validate(i) async for i in self._docs.read_all_items()]

    async def delete(self, document_id):
        from azure.cosmos.exceptions import CosmosResourceNotFoundError

        await self._init()
        try:
            await self._docs.delete_item(document_id, partition_key=document_id)
        except CosmosResourceNotFoundError:
            pass

    async def aclose(self) -> None:
        await self._client.close()


def build_store(settings: Settings) -> SQLiteStore | CosmosStore:
    if settings.session_store == "cosmos":
        return CosmosStore(settings)
    return SQLiteStore(settings.sqlite_path)

