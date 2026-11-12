"""Unit tests for all pipeline stages and cost/safety controls."""
from __future__ import annotations

import asyncio

import pytest

from app.config import Settings
from app.core.errors import RateLimited
from app.pipeline.abstention import ABSTENTION_MESSAGES, abstention_message
from app.pipeline.cache import InMemoryTTLCache, make_cache_key
from app.pipeline.generation import generate_answer
from app.pipeline.language import heuristic_detect
from app.pipeline.retrieval import resolve_versions, rrf_merge
from app.pipeline.verification import renumber_citations, unsupported_numbers, verify_answer
from app.rate_limit import SlidingWindowLimiter
from app.schemas import Candidate, Chunk, QueryUnderstanding
from app.services.chunking import chunk_pages, split_pages
from app.services.llm import LLMProvider, LLMResult
from pydantic import ValidationError


def test_language_detection_heuristics() -> None:
    en = heuristic_detect("What is the annual tuition fee for B.Tech?")
    assert en.language == "en" and en.script == "Latn" and en.english_confident is True

    hi = heuristic_detect("हॉस्टल में रात को वापस आने का समय क्या है?")
    assert hi.language == "hi" and hi.script == "Deva" and not hi.is_hinglish

    hinglish = heuristic_detect("B.Tech ki annual fee kitni hai?")
    assert hinglish.language == "hi-Latn" and hinglish.is_hinglish is True

    ta = heuristic_detect("விடுதி இரவு நேரம் என்ன?")
    assert ta.language == "ta" and ta.script == "Taml"


def test_rrf_merge_deterministic_and_monotonic() -> None:
    merged = rrf_merge([["c1", "c2", "c3"], ["c2", "c4", "c1"]], k=60)
    ids = [cid for cid, _ in merged]
    assert ids[0] == "c2"
    assert ids[1] == "c1"


def test_version_conflict_prefers_latest_effective_date() -> None:
    old = Candidate(
        chunk=Chunk(
            id="old-1",
            document_id="doc-old",
            document_name="Exam-Form-Circular-2025.pdf",
            blob_name="circulars/Exam-Form-Circular__2025-08-01__v1.pdf",
            page=1,
            content="Old fine ₹200",
            effective_date="2025-08-01",
            version="1",
        )
    )
    new = Candidate(
        chunk=Chunk(
            id="new-1",
            document_id="doc-new",
            document_name="Exam-Form-Circular-2026.pdf",
            blob_name="circulars/Exam-Form-Circular__2026-08-15__v2.pdf",
            page=1,
            content="New fine ₹500",
            effective_date="2026-08-15",
            version="2",
        )
    )
    kept, superseded = resolve_versions([old, new])
    assert [c.chunk.id for c in kept] == ["new-1"]
    assert "doc-old" in superseded


def test_chunking_preserves_page_numbers_and_tables() -> None:
    raw = "# Page One\n\nIntro paragraph.\n\n| Col A | Col B |\n| --- | --- |\n| 1 | ₹50,000 |\f# Page Two\n\nSecond page text."
    pages = split_pages(raw)
    drafts = chunk_pages(pages, max_tokens=200, overlap_tokens=30)
    assert [d.page for d in drafts] == [1, 2]
    assert "| 1 | ₹50,000 |" in drafts[0].text


def test_citation_renumbering_and_invalid_marker_removal() -> None:
    ans, order = renumber_citations("Hostel gate closes at 10:00 PM [3] and opens at 5:30 AM [99][1].", n_sources=4)
    assert ans == "Hostel gate closes at 10:00 PM [1] and opens at 5:30 AM [2]."
    assert order == [2, 0]


def test_numeric_and_script_numeral_fact_check() -> None:
    evidence = ["The annual fee is ₹1,25,000 and minimum attendance is 75%."]
    assert unsupported_numbers("शुल्क ₹१,२५,००० है और ७५% उपस्थिति ज़रूरी है [1].", evidence) == []
    assert unsupported_numbers("The annual fee is ₹125000 [1].", evidence) == []
    assert unsupported_numbers("The annual fee is ₹90,000 [1].", evidence) == ["90000"]


def test_verify_answer_converts_uncited_to_abstention() -> None:
    cand = Candidate(chunk=Chunk(id="c1", document_id="d1", document_name="doc.pdf", page=1, content="Fee is ₹50,000."))
    vr = verify_answer("Fee is ₹50,000 without citation.", [cand])
    assert vr.abstain is True and vr.reason == "no_valid_citations"


def test_abstention_localisation() -> None:
    for code in ("en", "hi", "hi-Latn", "ta", "te", "mr", "bn", "kn"):
        assert abstention_message(code) == ABSTENTION_MESSAGES[code]
    assert abstention_message("unknown-lang") == ABSTENTION_MESSAGES["en"]


def test_cache_and_rate_limiter() -> None:
    async def _run() -> None:
        now = 100.0
        cache = InMemoryTTLCache(max_items=2, clock=lambda: now)
        k1 = make_cache_key("What is the fee?", ["doc1"])
        k2 = make_cache_key("what is the fee", ["doc1"])
        assert k1 == k2
        await cache.set(k1, "val", ttl_seconds=10)
        assert await cache.get(k1) == "val"
        now += 11.0
        assert await cache.get(k1) is None

        limiter = SlidingWindowLimiter(2, 10, clock=lambda: now)
        await limiter.check("c1")
        await limiter.check("c1")
        with pytest.raises(RateLimited):
            await limiter.check("c1")

    asyncio.run(_run())


def test_generation_temperature_setting_and_forwarding() -> None:
    default_settings = Settings(_env_file=None)
    assert default_settings.generation_temperature == 0.0

    with pytest.raises(ValidationError):
        Settings(_env_file=None, generation_temperature=-0.1)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, generation_temperature=2.1)

    seen: list[float] = []

    class RecordingLLM(LLMProvider):
        async def _complete(self, messages, *, model, temperature, max_tokens, json_mode, task) -> LLMResult:
            seen.append(temperature)
            return LLMResult("Answer [1].", 10, 5, model)

    custom = Settings(_env_file=None, generation_temperature=0.35)
    qu = QueryUnderstanding(language="en", script="Latn", english_query="What is the fee?")
    cand = Candidate(chunk=Chunk(id="c1", document_id="d1", document_name="doc.pdf", page=1, content="Fee is ₹50,000."))
    asyncio.run(generate_answer("What is the fee?", qu, [cand], llm=RecordingLLM(), settings=custom))
    assert seen == [0.35]


