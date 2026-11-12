"""Offline evaluation runner over `eval/golden_set.jsonl`."""
from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from pathlib import Path

from app.config import Settings
from app.main import create_app


async def evaluate(golden_path: Path) -> dict:
    s = Settings(mock_azure=True, sqlite_path=":memory:").apply_mock_defaults()
    app = create_app(s)
    rows = [json.loads(line) for line in golden_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    by_lang: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "retrieval_hit": 0, "citation_ok": 0, "abstain_ok": 0})

    async with app.router.lifespan_context(app):
        pipeline = app.state.pipeline
        for item in rows:
            res = await pipeline.run(item["question"], None)
            lang = item["language"]
            stats = by_lang[lang]
            stats["total"] += 1
            if item["should_abstain"]:
                if res.abstained and not res.sources:
                    stats["abstain_ok"] += 1
                    stats["retrieval_hit"] += 1
                    stats["citation_ok"] += 1
            else:
                if not res.abstained and res.sources:
                    stats["abstain_ok"] += 1
                    hit = any(
                        src.document_name == item["expected_doc"] and src.page == item["expected_page"]
                        for src in res.sources
                    )
                    if hit:
                        stats["retrieval_hit"] += 1
                    if "[1]" in res.answer and hit:
                        stats["citation_ok"] += 1

    report: dict[str, dict[str, float | int]] = {}
    for lang, st in by_lang.items():
        n = max(1, st["total"])
        report[lang] = {
            "count": st["total"],
            "retrieval_hit_rate": round(st["retrieval_hit"] / n, 3),
            "citation_accuracy": round(st["citation_ok"] / n, 3),
            "abstention_accuracy": round(st["abstain_ok"] / n, 3),
        }
    return report


def main() -> None:
    path = Path(__file__).with_name("golden_set.jsonl")
    report = asyncio.run(evaluate(path))
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

