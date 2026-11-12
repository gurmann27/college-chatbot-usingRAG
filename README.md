# College Multilingual RAG Chatbot (Full-Stack Project)

This folder contains the complete full-stack project:

```text
college-rag-project/
├── college-rag-backend/        # FastAPI multilingual RAG backend (Python 3.11+)
│   ├── app/                    # API v1, RAG pipeline, Azure & Mock services, SQLite/Cosmos DB
│   ├── functions/blob_trigger/ # Azure Function trigger for blob ingestion
│   ├── scripts/                # create_index.py & ingest.py CLI tools
│   ├── tests/                  # Unit & end-to-end API acceptance tests
│   ├── eval/                   # Golden dataset & evaluation runner
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .env
├── college-rag-chat-frontend/  # React 18 + TypeScript + Vite + Tailwind UI
│   ├── src/
│   ├── package.json
│   ├── vite.config.ts
│   └── .env
├── docker-compose.yml
├── start.ps1                   # One-command launcher for Windows PowerShell
└── pyrightconfig.json          # IDE type-checking configuration
```

## Quick Start

### Option 1: One-click PowerShell Launcher
```powershell
.\start.ps1
```

### Option 2: Run Manually in Two Terminals

**Terminal 1 — Backend (`http://localhost:8000`)**
```powershell
cd college-rag-backend
C:\Users\gdsin\AppData\Local\Programs\Python\Python313\python.exe -m uvicorn app.main:app --reload --port 8000
```

**Terminal 2 — Frontend (`http://localhost:5173`)**
*(Requires Node.js LTS: `winget install OpenJS.NodeJS.LTS`)*
```powershell
cd college-rag-chat-frontend
npm install
npm run dev
```

### Run Backend Tests & Offline Evaluation
```powershell
cd college-rag-backend
C:\Users\gdsin\AppData\Local\Programs\Python\Python313\python.exe -m pytest -v
C:\Users\gdsin\AppData\Local\Programs\Python\Python313\python.exe -m eval.run_eval
```

