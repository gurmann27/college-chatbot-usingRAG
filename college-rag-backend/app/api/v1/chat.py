"""POST /api/v1/chat."""
from __future__ import annotations

import asyncio
import logging
import uuid

from fastapi import APIRouter, Depends, Request

from app.config import Settings
from app.core.errors import BudgetExceeded, UpstreamError
from app.core.logging import StageTimer
from app.core.text import scrub_pii, strip_control
from app.core.usage import TokenBudget, bind_budget, start_request_usage
from app.db.models import MessageRecord, utcnow
from app.db.repository import SessionRepository
from app.pipeline.abstention import busy_message
from app.pipeline.chat_pipeline import ChatPipeline, dumps_sources
from app.pipeline.language import heuristic_detect
from app.rate_limit import enforce_rate_limit
from app.schemas import ChatRequest, ChatResponse

log = logging.getLogger(__name__)
router = APIRouter()
TITLE_LEN = 44


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    request: Request,
    client_id: str = Depends(enforce_rate_limit),
) -> ChatResponse:
    state = request.app.state
    settings: Settings = state.settings
    budget: TokenBudget = state.budget
    if budget.exhausted():
        lang = heuristic_detect(body.query).language
        raise BudgetExceeded(busy_message(lang))

    usage = start_request_usage()
    bind_budget(budget)
    timer = StageTimer()
    pipeline: ChatPipeline = state.pipeline
    sessions: SessionRepository = state.sessions

    try:
        res = await asyncio.wait_for(
            pipeline.run(body.query, body.document_ids, timer), timeout=settings.chat_timeout_seconds
        )
    except asyncio.TimeoutError:
        raise UpstreamError("The request took too long. Please try a shorter or more specific question.") from None

    session_id = body.session_id or f"s-{uuid.uuid4().hex[:16]}"
    msg_id = f"m-{uuid.uuid4().hex[:16]}"
    clean_query = scrub_pii(strip_control(body.query))
    title = clean_query[:TITLE_LEN]

    with timer.stage("persist"):
        now = utcnow()
        await sessions.append_messages(
            client_id,
            session_id,
            title,
            [
                MessageRecord(id=f"u-{uuid.uuid4().hex[:16]}", role="user", content=clean_query, created_at=now),
                MessageRecord(
                    id=msg_id, role="assistant", content=res.answer, created_at=now,
                    sources=dumps_sources(res.sources), language=res.language, abstained=res.abstained,
                ),
            ],
        )

    log.info(
        "chat_completed",
        extra={
            "language": res.language,
            "intent": res.query.intent_category if res.query else None,
            "qu_source": res.query.source if res.query else None,
            "abstained": res.abstained,
            "reason": res.reason,
            "cache_hit": res.cache_hit,
            "sources": len(res.sources),
            "stages_ms": timer.stages,
            "total_ms": timer.total_ms,
            **usage.summary(),
            "estimated_cost_usd": usage.estimated_cost_usd(settings),
            "daily_tokens_used": budget.used,
        },
    )
    return ChatResponse(
        session_id=session_id, message_id=msg_id, answer=res.answer,
        language=res.language, abstained=res.abstained, sources=res.sources,
    )

