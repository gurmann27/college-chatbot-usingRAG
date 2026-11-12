"""GET /api/v1/documents (read-only view of the pre-indexed knowledge base)."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request

from app.db.models import iso
from app.db.repository import DocumentRegistry
from app.schemas import DocumentOut

router = APIRouter()
PublicStatus = Literal["indexed", "processing", "failed"]


def _public_status(status: str) -> PublicStatus | None:
    if status == "indexed":
        return "indexed"
    if status == "processing":
        return "processing"
    if status == "failed":
        return "failed"
    return None


@router.get("/documents", response_model=list[DocumentOut])
async def list_documents(request: Request) -> list[DocumentOut]:
    reg: DocumentRegistry = request.app.state.registry
    raw_docs = await reg.list()
    raw_docs.sort(key=lambda d: (d.name.lower(), d.id))
    out: list[DocumentOut] = []
    for d in raw_docs:
        st = _public_status(d.status)
        if st is None:
            continue
        out.append(
            DocumentOut(
                id=d.id,
                name=d.name,
                size_bytes=d.size_bytes,
                pages=d.pages,
                uploaded_at=iso(d.uploaded_at),
                status=st,
                category=d.category,
                effective_date=d.effective_date,
                version=d.version,
                language=d.language,
            )
        )
    return out

