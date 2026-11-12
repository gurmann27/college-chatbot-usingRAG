"""Admin-only endpoints (protected by ADMIN_API_KEY or Microsoft Entra ID role)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.auth import require_admin
from app.core.errors import NotFound
from app.schemas import ReindexResult
from app.services.ingestion import IngestionService

router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])


@router.post("/reindex", response_model=ReindexResult)
async def reindex_all(request: Request, force: bool = False) -> ReindexResult:
    ing: IngestionService = request.app.state.ingestion
    return await ing.sync_all(force=force)


@router.post("/reindex/{blob_name:path}", response_model=ReindexResult)
async def reindex_one(blob_name: str, request: Request) -> ReindexResult:
    ing: IngestionService = request.app.state.ingestion
    res = await ing.ingest_by_name(blob_name, force=True)
    if res.status == "not_found":
        raise NotFound("Blob not found in container.")
    return res


@router.delete("/documents/{document_id}")
async def delete_document(document_id: str, request: Request) -> dict[str, str]:
    ing: IngestionService = request.app.state.ingestion
    ok = await ing.delete_document(document_id, mark="superseded")
    if not ok:
        raise NotFound("Document not found.")
    return {"status": "superseded", "document_id": document_id}

