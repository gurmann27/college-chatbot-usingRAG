"""Chat pipeline orchestrator: wires the unit-testable steps (a)-(g) together."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

from app.config import Settings
from app.core.logging import StageTimer
from app.core.text import normalize_query, sha256
from app.pipeline.abstention import abstention_message
from app.pipeline.cache import AnswerCache
from app.pipeline.generation import generate_answer, render_in_language
from app.pipeline.language import understand_query
from app.pipeline.rerank import Reranker, apply_threshold
from app.pipeline.retrieval import retrieve
from app.pipeline.verification import faithfulness_judge, renumber_citations, unsupported_numbers, evidence_texts, verify_answer
from app.schemas import Candidate, QueryUnderstanding, SourceOut
from app.services.embeddings import EmbeddingProvider
from app.services.llm import LLMProvider
from app.services.search import SearchIndex

log = logging.getLogger(__name__)
SNIPPET_MAX_CHARS = 1200


@dataclass
class PipelineResult:
    answer: str
    language: str
    abstained: bool
    sources: list[SourceOut] = field(default_factory=list)
    reason: str = "ok"
    cache_hit: bool = False
    query: QueryUnderstanding | None = None


def to_source(c: Candidate, validated: bool) -> SourceOut:
    ch = c.chunk
    return SourceOut(
        id=ch.id, document_id=ch.document_id, document_name=ch.document_name, page=ch.page,
        score=round(max(0.0, min(1.0, c.score)), 4),
        snippet=ch.content[:SNIPPET_MAX_CHARS],  # original language, never translated
        validated=validated, category=ch.category, effective_date=ch.effective_date,
    )


class ChatPipeline:
    def __init__(
        self,
        *,
        settings: Settings,
        llm: LLMProvider,
        embeddings: EmbeddingProvider,
        search: SearchIndex,
        reranker: Reranker,
        cache: AnswerCache,
    ):
        self.s = settings
        self.llm = llm
        self.embeddings = embeddings
        self.search = search
        self.reranker = reranker
        self.cache = cache

    # ------------------------------------------------------------------ helpers
    def _abstain(self, qu: QueryUnderstanding, reason: str, cache_hit: bool = False) -> PipelineResult:
        return PipelineResult(abstention_message(qu.language), qu.language, True, [], reason, cache_hit, qu)

    async def _understand(self, query: str) -> QueryUnderstanding:
        key = f"qu:{sha256(normalize_query(query))[:40]}"
        hit = await self.cache.backend.get(key)
        if hit:
            return QueryUnderstanding.model_validate_json(hit)
        qu = await understand_query(query, self.llm, self.s)
        if qu.source != "fallback":  # do not cache degraded results
            await self.cache.backend.set(key, qu.model_dump_json(), self.s.cache_ttl_seconds)
        return qu

    # ------------------------------------------------------------------ main
    async def run(self, query: str, document_ids: list[str] | None, timer: StageTimer | None = None) -> PipelineResult:
        timer = timer or StageTimer()

        with timer.stage("understand"):
            qu = await self._understand(query)

        with timer.stage("cache"):
            key = await self.cache.key(qu.english_query, document_ids)
            entry = await self.cache.get(key)
        if entry is not None:
            res = await self._from_cache(entry, key, qu, timer)
            if res is not None:
                return res

        with timer.stage("retrieve"):
            cands = await retrieve(
                qu, query, document_ids, search=self.search, embeddings=self.embeddings, settings=self.s
            )
        with timer.stage("rerank"):
            ranked = await self.reranker.rerank(qu, cands)
            passing = apply_threshold(ranked, self.s.relevance_threshold)

        if not passing:  # step (d): abstain WITHOUT calling the generation LLM
            return self._abstain(qu, "below_threshold")

        # Specific entity guard: if query specifies an unoffered program or concept (e.g. MBBS, Pilot, Helipad)
        # that does not appear in any candidate text, abstain so generic terms ('fee', 'course') don't match.
        unoffered_match = re.search(
            r"\b(MBBS|BDS|MD|MS|BAMS|BHMS|B\.?Pharm|M\.?Pharm|Pharmacy|Nursing|Dentistry|Dentist|Aviation|Pilot|Helipad|Airport)\b",
            query,
            re.I,
        )
        if unoffered_match:
            entity = unoffered_match.group(1).lower()
            all_cands_text = " ".join(c.text.lower() for c in passing)
            if entity not in all_cands_text:
                return self._abstain(qu, "unoffered_program")

        with timer.stage("generate"):
            answer, used = await generate_answer(query, qu, passing, llm=self.llm, settings=self.s)
        with timer.stage("verify"):
            vr = verify_answer(answer, used)
            if vr.unsupported:
                log.info("unsupported_facts", extra={"count": len(vr.unsupported)})
                if self.s.regenerate_on_unsupported_fact:
                    answer, used = await generate_answer(
                        query, qu, passing, llm=self.llm, settings=self.s, unsupported_facts=vr.unsupported
                    )
                    vr = verify_answer(answer, used)
                if vr.unsupported:
                    vr.abstain, vr.reason = True, "unsupported_facts"
            if not vr.abstain and self.s.faithfulness_check:
                ok, flags = await faithfulness_judge(vr.answer, vr.sources, llm=self.llm, settings=self.s)
                if not ok:
                    vr.abstain, vr.reason = True, "judge_rejected"
                vr.validated = flags

        if vr.abstain:
            return self._abstain(qu, vr.reason)

        sources = [to_source(c, v) for c, v in zip(vr.sources, vr.validated)]
        await self.cache.put(key, {
            "abstained": False,
            "candidates": [c.model_dump() for c in vr.sources],
            "validated": vr.validated,
            "answers": {qu.language: vr.answer},
        })
        return PipelineResult(vr.answer, qu.language, False, sources, "ok", False, qu)

    async def _from_cache(self, entry: dict, key: str, qu: QueryUnderstanding, timer: StageTimer) -> PipelineResult | None:
        if entry.get("abstained"):
            return self._abstain(qu, entry.get("reason", "cached"), cache_hit=True)
        cands = [Candidate.model_validate(c) for c in entry.get("candidates", [])]
        validated = entry.get("validated") or [True] * len(cands)
        sources = [to_source(c, v) for c, v in zip(cands, validated)]
        answers: dict[str, str] = entry.get("answers", {})
        if qu.language in answers:
            return PipelineResult(answers[qu.language], qu.language, False, sources, "ok", True, qu)
        if not answers or not cands:
            return None
        # Re-render the cached (preferably English) answer in the user's language.
        base = answers.get("en") or next(iter(answers.values()))
        with timer.stage("render"):
            try:
                rendered = await render_in_language(base, qu, llm=self.llm, settings=self.s)
            except Exception:
                return None  # fall back to the full pipeline
        new, order = renumber_citations(rendered, len(cands))
        evidence = [t for c in cands for t in evidence_texts(c)]
        # the re-render must keep every citation and must not introduce new numbers
        if sorted(order) != list(range(len(cands))) or unsupported_numbers(new, evidence):
            return None
        # keep the cached source order (rendering must not reorder sources)
        if order != list(range(len(cands))):
            return None
        answers[qu.language] = new
        entry["answers"] = answers
        await self.cache.put(key, entry)
        return PipelineResult(new, qu.language, False, sources, "ok", True, qu)


def dumps_sources(sources: list[SourceOut]) -> list[dict]:
    return [json.loads(s.model_dump_json()) for s in sources]

