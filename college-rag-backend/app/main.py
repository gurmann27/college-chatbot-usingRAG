"""FastAPI application entry point for the multilingual College RAG backend."""
from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from app.api.v1 import admin, chat, documents, history
from app.ui import INDEX_HTML
from app.config import Settings, get_settings
from app.core.errors import AppError
from app.core.logging import configure_logging, request_id_var
from app.core.usage import TokenBudget
from app.db.repository import build_store
from app.pipeline.cache import AnswerCache, build_cache
from app.pipeline.chat_pipeline import ChatPipeline
from app.pipeline.rerank import build_reranker
from app.rate_limit import SlidingWindowLimiter
from app.services.embeddings import CachedEmbeddings, build_embeddings
from app.services.ingestion import IngestionService
from app.services.llm import build_llm
from app.services.search import build_search
from app.services.storage import build_storage

log = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        get_settings.cache_clear()
    s = (settings or get_settings()).apply_mock_defaults()
    configure_logging(s.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        budget = TokenBudget(s.daily_token_budget)
        cache_backend = build_cache(s.cache_backend, redis_url=s.redis_url, max_items=s.cache_max_items)
        answer_cache = AnswerCache(cache_backend, s.cache_ttl_seconds)
        raw_embeddings = build_embeddings(s, budget)
        embeddings = CachedEmbeddings(raw_embeddings, cache_backend, s.embedding_cache_ttl_seconds)
        llm = build_llm(s, budget)
        search = build_search(s)
        storage = build_storage(s)
        store = build_store(s)
        reranker = build_reranker(s, llm)
        ingestion = IngestionService(
            storage=storage,
            search=search,
            embeddings=embeddings,
            registry=store,
            cache=answer_cache,
            settings=s,
        )
        pipeline = ChatPipeline(
            settings=s,
            llm=llm,
            embeddings=embeddings,
            search=search,
            reranker=reranker,
            cache=answer_cache,
        )

        app.state.settings = s
        app.state.budget = budget
        app.state.cache_backend = cache_backend
        app.state.answer_cache = answer_cache
        app.state.embeddings = embeddings
        app.state.llm = llm
        app.state.search = search
        app.state.storage = storage
        app.state.sessions = store
        app.state.registry = store
        app.state.ingestion = ingestion
        app.state.pipeline = pipeline
        app.state.rate_limiter = SlidingWindowLimiter(
            s.rate_limit_per_minute, s.global_rate_limit_per_minute
        )

        if s.mock_azure:
            res = await ingestion.sync_all(force=True)
            log.info(
                "mock_corpus_ready",
                extra={"processed": res.processed, "skipped": res.skipped, "failed": res.failed},
            )
            try:
                import json
                from pathlib import Path
                test_queries = [
                    "What programs are offered under the School of Artificial Intelligence?",
                    "What are the hangout joints and food options on the Bennett University campus?",
                    "Who is the Vice Chancellor and who are the Deans at Bennett University?",
                    "Which companies visit Bennett University for placements?",
                    "School of Artificial Intelligence me kaunse programs offer hote hain?",
                    "Bennett University me kitne startups launch hue hain?",
                    "बेनेट यूनिवर्सिटी में आर्टिफिशियल इंटेलिजेंस के कौन से प्रोग्राम हैं?",
                    "हॉस्टल में रात को वापस आने का समय क्या है?",
                    "हवाई जहाज पायलट कोर्स की फीस क्या है?",
                ]
                results_out = []
                for tq in test_queries:
                    r = await pipeline.run(tq, None)
                    results_out.append({
                        "query": tq,
                        "language": r.language,
                        "abstained": r.abstained,
                        "reason": r.reason,
                        "page": r.sources[0].page if r.sources else None,
                        "doc": r.sources[0].document_name if r.sources else None,
                        "answer": r.answer,
                    })
                (Path(__file__).resolve().parents[1] / "data" / "self_test.json").write_text(
                    json.dumps(
                        {
                            "processed_docs": res.processed,
                            "results": results_out,
                        },
                        indent=2,
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
            except Exception as exc:
                log.warning("self_test_failed", extra={"error": str(exc)})
            if s.azure_storage_connection_string.get_secret_value():
                import json
                from pathlib import Path
                status_file = Path(__file__).resolve().parents[1] / "data" / "azure_upload_status.json"
                try:
                    from app.services.storage import AzureBlobStorage

                    brochure_blob = "admissions/Bennett-Brochure__2026-11-12__v1.pdf"
                    info = await storage.get_info(brochure_blob)
                    if info is not None:
                        data = await storage.download(brochure_blob)
                        az = AzureBlobStorage(s)
                        try:
                            up = await az.upload(brochure_blob, data, metadata=info.metadata)
                            log.info("azure_blob_synced", extra={"blob_name": brochure_blob, "size": len(data)})
                            status_file.parent.mkdir(parents=True, exist_ok=True)
                            status_file.write_text(
                                json.dumps(
                                    {
                                        "ok": True,
                                        "container": s.blob_container,
                                        "blob_name": up.name,
                                        "size_bytes": up.size,
                                        "etag": up.etag,
                                    },
                                    indent=2,
                                ),
                                encoding="utf-8",
                            )
                        finally:
                            await az.aclose()
                except Exception as exc:
                    log.warning("azure_blob_sync_skipped", extra={"error": type(exc).__name__})
                    status_file.parent.mkdir(parents=True, exist_ok=True)
                    status_file.write_text(
                        json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, indent=2),
                        encoding="utf-8",
                    )
        try:
            yield
        finally:
            await llm.aclose()
            await embeddings.aclose()
            await search.aclose()
            await storage.aclose()
            await store.aclose()
            await cache_backend.aclose()

    app = FastAPI(title=s.app_name, version="1.0.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Client-Id", "X-Admin-Api-Key", "X-Request-Id"],
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        rid = (request.headers.get("X-Request-Id") or "").strip()[:64] or uuid.uuid4().hex[:16]
        token = request_id_var.set(rid)
        try:
            response = await call_next(request)
            response.headers["X-Request-Id"] = rid
            return response
        finally:
            request_id_var.reset(token)

    @app.exception_handler(AppError)
    async def handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
        headers = {"Retry-After": str(exc.retry_after)} if exc.retry_after else None
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.public_message}, headers=headers)

    @app.exception_handler(HTTPException)
    async def handle_http_error(_request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": str(exc.detail)})

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        msgs = [f"{'.'.join(str(p) for p in e.get('loc', []))}: {e.get('msg', '')}" for e in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": "; ".join(msgs) or "Invalid request."})

    @app.exception_handler(Exception)
    async def handle_unexpected(_request: Request, exc: Exception) -> JSONResponse:
        log.error("unhandled_error", extra={"error": type(exc).__name__}, exc_info=exc)
        return JSONResponse(status_code=500, content={"detail": "Internal server error."})

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def root_ui() -> HTMLResponse:
        return HTMLResponse(content=INDEX_HTML)

    @app.post("/api/v1/cloud-sync", include_in_schema=False)
    async def cloud_sync(request: Request, document_id: str | None = None) -> dict[str, str | int | bool]:
        from pathlib import Path
        from app.config import Settings
        from app.services.storage import AzureBlobStorage

        env_path = Path(__file__).resolve().parents[1] / ".env"
        fresh_s = Settings(_env_file=env_path)
        storage = request.app.state.storage
        registry = request.app.state.registry

        target_blob = "admissions/Bennett-Brochure__2026-11-12__v1.pdf"
        if document_id:
            rec = await registry.get(document_id)
            if rec is not None and rec.blob_name:
                target_blob = rec.blob_name

        info = await storage.get_info(target_blob)
        if info is None:
            raise HTTPException(status_code=404, detail=f"{target_blob} not found in local blob storage.")
        data = await storage.download(target_blob)
        try:
            az = AzureBlobStorage(fresh_s)
            try:
                up = await az.upload(target_blob, data, metadata=info.metadata)
            finally:
                await az.aclose()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {
            "uploaded": True,
            "container": fresh_s.blob_container,
            "blob_name": up.name,
            "size_bytes": up.size,
            "etag": up.etag,
        }

    @app.post("/api/v1/upload-file", include_in_schema=False)
    async def upload_file(
        request: Request,
        filename: str = "document.pdf",
        category: str = "admissions",
    ) -> dict[str, str | int | bool | None]:
        from datetime import date
        from pathlib import Path
        import re
        from app.config import Settings
        from app.services.storage import AzureBlobStorage

        data = await request.body()
        if not data:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        safe_name = Path(filename).name
        stem = re.sub(r"[^A-Za-z0-9_\-. ]+", "-", Path(safe_name).stem).strip() or "Document"
        ext = Path(safe_name).suffix.lower() or ".pdf"
        today_str = date.today().isoformat()
        cat = category.lower().strip() or "admissions"
        blob_name = f"{cat}/{stem}__{today_str}__v1{ext}"
        meta = {
            "category": cat,
            "effective_date": today_str,
            "version": "1",
            "title": safe_name,
        }

        storage = request.app.state.storage
        ingestion = request.app.state.ingestion
        registry = request.app.state.registry
        await storage.upload(blob_name, data, metadata=meta)
        ingest_res = await ingestion.ingest_by_name(blob_name, force=True)

        azure_synced = False
        azure_error: str | None = None
        env_path = Path(__file__).resolve().parents[1] / ".env"
        fresh_s = Settings(_env_file=env_path)
        if fresh_s.azure_storage_connection_string.get_secret_value() or fresh_s.azure_storage_account_url:
            try:
                az = AzureBlobStorage(fresh_s)
                try:
                    await az.upload(blob_name, data, metadata=meta)
                    azure_synced = True
                finally:
                    await az.aclose()
            except Exception as exc:
                azure_error = str(exc)

        doc_id = ingest_res.details[0]["document_id"] if ingest_res.details else None
        rec = await registry.get(doc_id) if doc_id else None
        return {
            "status": "ok",
            "blob_name": blob_name,
            "document_id": doc_id,
            "name": rec.name if rec else safe_name,
            "pages": rec.pages if rec else None,
            "azure_synced": azure_synced,
            "azure_error": azure_error,
        }

    @app.get("/api/v1/health")
    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(chat.router, prefix="/api/v1")
    app.include_router(history.router, prefix="/api/v1")
    app.include_router(documents.router, prefix="/api/v1")
    app.include_router(admin.router, prefix="/api/v1")
    return app


app = create_app()

