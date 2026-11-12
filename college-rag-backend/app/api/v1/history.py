"""GET /api/v1/history and DELETE /api/v1/history/{session_id}."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status

from app.auth import resolve_client_id
from app.db.models import iso
from app.db.repository import SessionRepository
from app.schemas import MessageOut, SessionOut, SourceOut

router = APIRouter()


@router.get("/history", response_model=list[SessionOut])
async def get_history(request: Request, client_id: str = Depends(resolve_client_id)) -> list[SessionOut]:
    repo: SessionRepository = request.app.state.sessions
    sessions = await repo.list_sessions(client_id)
    return [
        SessionOut(
            id=s.id,
            title=s.title,
            created_at=iso(s.created_at),
            updated_at=iso(s.updated_at),
            messages=[
                MessageOut(
                    id=m.id,
                    role="user" if m.role == "user" else "assistant",
                    content=m.content,
                    sources=[SourceOut.model_validate(src) for src in m.sources],
                    created_at=iso(m.created_at),
                )
                for m in s.messages
            ],
        )
        for s in sessions
    ]


@router.delete("/history/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str, request: Request, client_id: str = Depends(resolve_client_id)
) -> Response:
    repo: SessionRepository = request.app.state.sessions
    await repo.delete_session(client_id, session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

