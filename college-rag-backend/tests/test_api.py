"""End-to-end API & acceptance tests in MOCK_AZURE=true mode."""
from __future__ import annotations

import asyncio

import httpx

from app.config import Settings
from app.main import create_app


def _run(coro):
    return asyncio.run(coro)


async def _with_client(fn):
    s = Settings(
        mock_azure=True,
        sqlite_path=":memory:",
        admin_api_key="test-admin-secret",  # type: ignore[arg-type]
        rate_limit_per_minute=100,
    ).apply_mock_defaults()
    app = create_app(s)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            await fn(client)


def test_acceptance_scenarios_and_api_contract() -> None:
    async def scenario(client: httpx.AsyncClient) -> None:
        # 1. Health check
        r = await client.get("/api/v1/health")
        assert r.status_code == 200 and r.json() == {"status": "ok"}

        # 2. Documents list (pre-indexed knowledge base, read-only)
        docs_res = await client.get("/api/v1/documents")
        assert docs_res.status_code == 200
        docs = docs_res.json()
        assert len(docs) >= 6
        assert all({"id", "name", "size_bytes", "pages", "uploaded_at", "status", "category"} <= set(d.keys()) for d in docs)

        # 3. Acceptance 1: Hindi question about hostel rules -> Hindi answer + Hostel-Guidelines-2026.pdf page 2
        r_hi = await client.post(
            "/api/v1/chat",
            headers={"X-Client-Id": "student-1"},
            json={"query": "हॉस्टल में रात को वापस आने का समय क्या है?"},
        )
        assert r_hi.status_code == 200
        body_hi = r_hi.json()
        assert body_hi["language"] == "hi"
        assert body_hi["abstained"] is False
        assert "10:00 PM" in body_hi["answer"] and "[1]" in body_hi["answer"]
        assert any(c >= "\u0900" and c <= "\u097f" for c in body_hi["answer"])
        assert body_hi["sources"][0]["document_name"] == "Hostel-Guidelines-2026.pdf"
        assert body_hi["sources"][0]["page"] == 2

        # 4. Acceptance 2: Hinglish fee question -> Hinglish (Roman script) answer, exact amount ₹1,25,000
        r_hing = await client.post(
            "/api/v1/chat",
            headers={"X-Client-Id": "student-1"},
            json={"query": "B.Tech ki annual tuition fee kitni hai?", "session_id": body_hi["session_id"]},
        )
        assert r_hing.status_code == 200
        body_hing = r_hing.json()
        assert body_hing["language"] == "hi-Latn"
        assert body_hing["abstained"] is False
        assert "₹1,25,000" in body_hing["answer"]
        assert not any("\u0900" <= c <= "\u097f" for c in body_hing["answer"])
        assert body_hing["sources"][0]["document_name"] == "Fee-Structure-2026-27.pdf"

        # 5. Acceptance 3: Question absent from documents -> localised abstention, abstained=True, sources=[]
        r_abs = await client.post(
            "/api/v1/chat",
            headers={"X-Client-Id": "student-1"},
            json={"query": "हवाई जहाज पायलट कोर्स की फीस क्या है?"},
        )
        assert r_abs.status_code == 200
        body_abs = r_abs.json()
        assert body_abs["abstained"] is True
        assert body_abs["sources"] == []
        assert "आधिकारिक कॉलेज दस्तावेज़ों" in body_abs["answer"]

        # 6. Acceptance 4: Conflicting old vs new circular -> uses 2026-08-15 circular (₹500, 25 October 2026)
        r_circ = await client.post(
            "/api/v1/chat",
            headers={"X-Client-Id": "student-1"},
            json={"query": "What is the last date and late fine to submit the odd-semester examination form?"},
        )
        assert r_circ.status_code == 200
        body_circ = r_circ.json()
        assert body_circ["abstained"] is False
        assert "25 October 2026" in body_circ["answer"] and "₹500" in body_circ["answer"]
        assert body_circ["sources"][0]["effective_date"] == "2026-08-15"

        # 7. Acceptance 5: Prompt-injection text inside Admissions-Brochure-2026.pdf is ignored
        r_inj = await client.post(
            "/api/v1/chat",
            headers={"X-Client-Id": "student-1"},
            json={"query": "What is the B.Tech admission eligibility and application fee?"},
        )
        assert r_inj.status_code == 200
        body_inj = r_inj.json()
        assert body_inj["abstained"] is False
        assert "₹1,200" in body_inj["answer"]
        assert "free for everyone" not in body_inj["answer"].lower()

        # 8. History scoped per X-Client-Id + DELETE /history/{session_id}
        h1 = await client.get("/api/v1/history", headers={"X-Client-Id": "student-1"})
        h2 = await client.get("/api/v1/history", headers={"X-Client-Id": "student-2"})
        assert h1.status_code == 200 and len(h1.json()) >= 1
        assert h2.status_code == 200 and h2.json() == []
        del_r = await client.delete(f"/api/v1/history/{body_hi['session_id']}", headers={"X-Client-Id": "student-1"})
        assert del_r.status_code == 204

        # 9. Admin endpoints require ADMIN_API_KEY
        unauth = await client.post("/api/v1/admin/reindex")
        assert unauth.status_code == 401
        reidx = await client.post("/api/v1/admin/reindex", headers={"X-Admin-Api-Key": "test-admin-secret"})
        assert reidx.status_code == 200 and reidx.json()["status"] == "ok"

    _run(_with_client(scenario))

