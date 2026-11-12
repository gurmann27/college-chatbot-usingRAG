"""CLI to upload a document to Azure Blob Storage (`college-docs` container) and ingest it.

Usage:
    python -m scripts.upload_blob --file "../Bennett-Brochure.pdf" --category admissions --effective-date 2026-11-12 --version 1
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import date
import json
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import get_settings
from app.db.repository import build_store
from app.pipeline.cache import AnswerCache, build_cache
from app.schemas import CATEGORIES
from app.services.embeddings import build_embeddings
from app.services.ingestion import IngestionService
from app.services.mock.storage import LocalFolderStorage
from app.services.search import build_search
from app.services.storage import AzureBlobStorage, build_storage


def build_blob_name(file_path: Path, category: str, effective_date: str, version: str) -> str:
    stem = file_path.stem
    ext = file_path.suffix.lower()
    ver = version.lstrip("vV") or "1"
    return f"{category}/{stem}__{effective_date}__v{ver}{ext}"


async def upload_and_ingest(
    *,
    file_path: Path,
    category: str,
    effective_date: str,
    version: str,
    title: str | None = None,
    blob_name: str | None = None,
) -> dict:
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    data = file_path.read_bytes()
    cat = category.lower().strip()
    if cat not in CATEGORIES:
        cat = "other"
    ver = version.lstrip("vV") or "1"
    doc_title = title or file_path.name
    target_blob = (blob_name or build_blob_name(file_path, cat, effective_date, ver)).replace("\\", "/").lstrip("/")
    metadata = {
        "category": cat,
        "effective_date": effective_date,
        "version": ver,
        "title": doc_title,
    }

    s = get_settings()

    # Always stage into local container directory so MOCK_AZURE=true and local dev have the blob immediately
    local_storage = LocalFolderStorage()
    local_info = await local_storage.upload(target_blob, data, metadata=metadata)

    azure_uploaded = False
    azure_account_Or_container = s.blob_container
    has_azure_creds = bool(s.azure_storage_connection_string.get_secret_value() or s.azure_storage_account_url)
    if has_azure_creds:
        az_storage = AzureBlobStorage(s)
        try:
            await az_storage.upload(target_blob, data, metadata=metadata)
            azure_uploaded = True
        finally:
            await az_storage.aclose()

    # Run ingestion pipeline so the document is immediately indexed
    storage = build_storage(s)
    search = build_search(s)
    embeddings = build_embeddings(s)
    store = build_store(s)
    cache = AnswerCache(build_cache(s.cache_backend, redis_url=s.redis_url), s.cache_ttl_seconds)
    ing = IngestionService(
        storage=storage, search=search, embeddings=embeddings, registry=store, cache=cache, settings=s
    )
    try:
        ingest_res = await ing.ingest_by_name(target_blob, force=True)
        doc_rec = None
        if ingest_res.details:
            doc_id = ingest_res.details[0]["document_id"]
            doc_rec = await store.get(doc_id)
        return {
            "blob_name": target_blob,
            "container": azure_account_Or_container,
            "size_bytes": local_info.size,
            "etag": local_info.etag,
            "metadata": metadata,
            "uploaded_to_local_blob_container": True,
            "uploaded_to_azure_cloud": azure_uploaded,
            "ingestion": ingest_res.model_dump(),
            "document_record": doc_rec.model_dump(mode="json") if doc_rec else None,
        }
    finally:
        await embeddings.aclose()
        await search.aclose()
        await storage.aclose()
        await store.aclose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload a document to college-docs blob storage and ingest it.")
    parser.add_argument("--file", required=True, help="Path to local PDF/DOCX/TXT/MD file")
    parser.add_argument("--category", default="admissions", choices=list(CATEGORIES), help="Document category")
    parser.add_argument("--effective-date", default=date.today().isoformat(), help="Effective date (YYYY-MM-DD)")
    parser.add_argument("--version", default="1", help="Document version (e.g. 1, 2)")
    parser.add_argument("--title", default=None, help="Display title override")
    parser.add_argument("--blob-name", default=None, help="Explicit blob path inside container")
    args = parser.parse_args()

    out = asyncio.run(
        upload_and_ingest(
            file_path=Path(args.file).resolve(),
            category=args.category,
            effective_date=args.effective_date,
            version=args.version,
            title=args.title,
            blob_name=args.blob_name,
        )
    )
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()

