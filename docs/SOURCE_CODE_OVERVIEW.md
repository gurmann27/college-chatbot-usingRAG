# Source Code Structure & Architecture Reference

This document provides a component-by-component overview of the source code for the **Multilingual College RAG Chatbot**.

---

## 1. Directory Tree

```text
college-rag-project-latest/
├── college-rag-backend/              # FastAPI Python Backend (Python 3.11+)
│   ├── app/
│   │   ├── main.py                  # FastAPI factory, lifespan, CORS, rate limiting
│   │   ├── config.py                # Pydantic Settings (.env configuration)
│   │   ├── ui.py                    # Built-in direct HTML/JS fallback interface
│   │   ├── rate_limit.py            # Sliding window in-memory rate limiter
│   │   ├── api/v1/                  # REST API Endpoints
│   │   │   ├── chat.py              # POST /api/v1/chat (Core RAG inference)
│   │   │   ├── documents.py         # GET /api/v1/documents & POST /api/v1/upload
│   │   │   ├── history.py           # GET /api/v1/history & DELETE /api/v1/history/{id}
│   │   │   └── admin.py             # Re-indexing and health monitoring
│   │   ├── pipeline/                # Retrieval & Generation Engine
│   │   │   ├── chat_pipeline.py     # Orchestrates retrieval, prompt, LLM & citation validation
│   │   │   ├── cache.py             # TTL-based query answer caching
│   │   │   └── rerank.py            # Cross-encoder / RRF re-ranking module
│   │   ├── services/                # Pluggable Service Abstractions
│   │   │   ├── search.py            # Azure AI Search / In-memory BM25 + Vector hybrid index
│   │   │   ├── embeddings.py        # OpenAI text-embedding-3-small / Mock hash embeddings
│   │   │   ├── llm.py               # Azure OpenAI / Mock deterministic grounded LLM
│   │   │   ├── storage.py           # Azure Blob Storage client / local filesystem adapter
│   │   │   └── ingestion.py         # Document parser, PDF chunker, and vectorizer
│   │   ├── db/                      # Persistence Layer
│   │   │   └── repository.py        # SQLite / Azure Cosmos DB session & message store
│   │   └── core/                    # Cross-cutting Utilities
│   │       ├── errors.py            # Standardized application exception types
│   │       ├── logging.py           # Structured JSON logger with request_id tracing
│   │       └── usage.py             # Daily token budget enforcer
│   ├── data/                        # Persistent storage (rag.db, sample PDF circulars)
│   ├── eval/                        # Evaluation Suite
│   │   ├── golden_set.jsonl         # Multilingual benchmark evaluation pairs
│   │   └── run_eval.py              # Automated offline evaluation runner
│   ├── scripts/
│   │   ├── ingest.py                # Standalone CLI document ingestion tool
│   │   └── create_index.py          # Azure AI Search index initializer
│   ├── Dockerfile                   # Production container definition
│   ├── requirements.txt             # Python backend dependencies
│   └── .env                         # Environment settings (Azure credentials & flags)
│
├── college-rag-chat-frontend/        # React 18 + Vite + TypeScript Frontend
│   ├── src/
│   │   ├── main.tsx                 # React DOM mount point
│   │   ├── App.tsx                  # Main layout, drawer state, and document filter
│   │   ├── types.ts                 # Message, SourceChunk, ChatSession, and API contracts
│   │   ├── components/
│   │   │   ├── ChatWindow.tsx       # Message list, auto-scroller, and empty state
│   │   │   ├── ChatInput.tsx        # Auto-resizing textarea & document filter picker
│   │   │   ├── MessageBubble.tsx    # User / Assistant message cards with citation badges
│   │   │   ├── SourceCitationCard.tsx # Accordion with snippet preview, page, and match score
│   │   │   ├── MarkdownRenderer.tsx # ReactMarkdown with syntax highlighting & [n] pill badges
│   │   │   ├── Sidebar.tsx          # Chat history, session management, and new chat trigger
│   │   │   └── DocumentPanel.tsx    # Upload modal with indexed document overview
│   │   ├── hooks/
│   │   │   ├── useChatStore.ts      # Active session management & localStorage caching
│   │   │   └── useDocuments.ts      # Indexed document state & periodic refresh
│   │   └── services/
│   │       ├── api.ts               # HTTP client (fetch + XHR upload) and response normalizers
│   │       └── mock.ts              # In-browser zero-dependency client mock
│   ├── dist/                        # Production build (pre-compiled HTML, CSS, JS)
│   ├── package.json                 # Node.js dependencies
│   ├── tailwind.config.js           # Modern Apple/clean aesthetic styling
│   └── vite.config.ts               # Vite build configuration
│
├── .github/workflows/
│   └── main_ragchatbot.yml          # GitHub Actions deployment to Azure App Service
├── main.py                          # Top-level Azure App Service entrypoint
├── startup.sh                       # Azure App Service Linux startup script
├── start.bat                        # Windows 1-click launcher (launches both in 2 terminals)
├── start.ps1                        # PowerShell dual-terminal launcher
├── run-backend.bat                  # Dedicated backend terminal script
├── run-frontend.bat                 # Dedicated frontend terminal script
└── docs/                            # Documentation, IEEE report & Dataset specification
    ├── IEEE_Project_Report.tex      # Full IEEE-formatted academic project report (LaTeX)
    ├── DATASET_REFERENCE.md         # Complete corpus, schemas, and golden benchmark spec
    └── SOURCE_CODE_OVERVIEW.md      # This file
```

---

## 2. Key Architecture Patterns in the Code

### 1. Dual Mode: Zero-Cost Local Mock vs. Real Azure Cloud
The backend is built around a single configuration flag: `MOCK_AZURE=true` in `.env`.
- When `MOCK_AZURE=true`:
  - Search runs completely in-memory using BM25 and feature-hashed cross-lingual embeddings.
  - LLM synthesis runs a deterministic extractive grounded model.
  - Storage reads from `./data/college-docs/`.
  - Sessions persist to SQLite (`./data/rag.db`).
  - **Zero cloud credentials or costs needed!**
- When `MOCK_AZURE=false`:
  - Search connects to **Azure AI Search** (`college-docs-index`).
  - LLM and embeddings connect to **Azure OpenAI** (`gpt-4o-mini` and `text-embedding-3-small`).
  - Storage reads from **Azure Blob Storage** (`college-docs` container).
  - Sessions can store in **Azure Cosmos DB** or **SQLite**.

### 2. Reciprocal Rank Fusion (RRF) Retrieval (`app/services/search.py`)
Queries are executed concurrently across lexical (BM25) and dense vector spaces:
$$\text{RRF\_Score}(d) = \frac{1}{60 + \text{Rank}_{\text{BM25}}(d)} + \frac{1}{60 + \text{Rank}_{\text{Dense}}(d)}$$
This guarantees that exact circular numbers (e.g. `Exam-Circular-2026-v2`) and conceptual semantic questions (e.g. `"hostel curfew time"`) rank accurately in top-4 candidates.

### 3. Verification & Dynamic Citation Renumbering (`app/pipeline/chat_pipeline.py`)
Answers from the LLM are passed through a verification parser:
- Extracts all `[n]` bracket citations.
- Validates that citation `[n]` corresponds to an actual document chunk delivered in the context.
- Renumbers citations so that `[1]` always matches the top-ranked source displayed in the frontend citation accordion card.
- If similarity falls below `RELEVANCE_THRESHOLD=0.25`, the pipeline triggers localized abstention:
  - English: *"Official college documents do not contain this information."*
  - Hindi: *"आधिकारिक कॉलेज दस्तावेज़ों में यह जानकारी नहीं मिली।"*

---

## 3. Core REST API Contract

| HTTP Method & Endpoint | Payload / Parameters | Response Schema | Purpose |
| :--- | :--- | :--- | :--- |
| `POST /api/v1/chat` | `{"query": "...", "session_id": "...", "document_ids": [...]}` | `{"session_id": "...", "answer": "...", "sources": [{"id": "...", "document_name": "...", "page": 1, "score": 0.88, "snippet": "..."}]}` | Main RAG inquiry endpoint |
| `GET /api/v1/history` | None | `[{"id": "...", "title": "...", "created_at": "...", "messages": [...]}]` | Fetches saved chat sessions |
| `DELETE /api/v1/history/{id}` | Path parameter `id` | `204 No Content` | Deletes a conversation session |
| `GET /api/v1/documents` | None | `[{"id": "...", "name": "...", "size_bytes": 1024, "pages": 12, "status": "indexed"}]` | Lists all searchable circulars |
| `POST /api/v1/upload` | `multipart/form-data` with `file` | `{"id": "...", "name": "...", "status": "indexed"}` | Dynamic document upload & indexing |
| `GET /docs` | None | Swagger UI | Interactive API documentation |

---

## 4. How to Run the Code

### Local Dual-Terminal Run:
```cmd
.\start.bat
```
- Backend runs on `http://localhost:8000`
- Frontend runs on `http://localhost:5173`

### Run Offline Accuracy Evaluation:
```powershell
cd college-rag-backend
C:\Users\gdsin\AppData\Local\Programs\Python\Python313\python.exe -m eval.run_eval
```
