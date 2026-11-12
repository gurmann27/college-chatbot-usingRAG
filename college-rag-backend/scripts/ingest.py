"""CLI for incremental or full ingestion: `python -m scripts.ingest --all`."""
from __future__ import annotations

import argparse
import asyncio
import json

from app.config import get_settings
from app.db.repository import build_store
from app.pipeline.cache import AnswerCache, build_cache
from app.services.embeddings import build_embeddings
from app.services.ingestion import IngestionService
from app.services.search import build_search
from app.services.storage import build_storage


async def run_cli(*, blob: str | None, force: bool) -> dict:
    s = get_settings()
    storage = build_storage(s)
    search = build_search(s)
    embeddings = build_embeddings(s)
    store = build_store(s)
    cache = AnswerCache(build_cache(s.cache_backend, redis_url=s.redis_url), s.cache_ttl_seconds)
    ing = IngestionService(
        storage=storage, search=search, embeddings=embeddings, registry=store, cache=cache, settings=s
    )
    try:
        res = await (ing.ingest_by_name(blob, force=force) if blob else ing.sync_all(force=force))
        return res.model_dump()
    finally:
        await embeddings.aclose()
        await search.aclose()
        await storage.aclose()
        await store.aclose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest blobs from college-docs container.")
    parser.add_argument("--all", action="store_true", help="Sync all blobs in the container")
    parser.add_argument("--blob", type=str, default=None, help="Ingest a single blob path")
    parser.add_argument("--force", action="store_true", help="Re-ingest even if fingerprint is unchanged")
    args = parser.parse_args()
    out = asyncio.run(run_cli(blob=args.blob, force=args.force))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()

