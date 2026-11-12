# College Multilingual RAG Backend

Cloud-native, multilingual Retrieval-Augmented Generation backend built with **FastAPI**, **Azure AI Search**, **Azure OpenAI**, **Azure Blob Storage**, and **SQLite / Azure Cosmos DB**.

## Key Capabilities
1. **Zero user-side document burden**: End users never upload files. Documents are pre-indexed from the `college-docs` Azure Blob container via an Azure Function trigger, CLI (`python -m scripts.ingest --all`), or admin endpoints.
2. **True cross-lingual retrieval**: Accepts queries in English, Hindi, Hinglish (`hi-Latn`), Tamil, Telugu, Marathi, Bengali, Kannada, etc., retrieves from English/multilingual documents via hybrid BM25 + dual-vector RRF, and answers in the user's exact language and script.
3. **Strict anti-hallucination with provenance**: Numbered context citations (`[1]`), citation renumbering, cross-script numeric/currency fact checking, prompt-injection stripping, and localised abstention when evidence is missing.
4. **Local zero-credential mode (`MOCK_AZURE=true`)**: Ships with an in-memory hybrid search index, cross-lingual feature-hashing embeddings, deterministic grounded LLM, and a 7-document college corpus.

## Blob Naming & Metadata Convention
Place documents inside the `college-docs` container using:
```text
<category>/<title>__<YYYY-MM-DD>__v<version>.<ext>
```
Example: `circulars/Exam-Form-Circular__2026-08-15__v2.pdf`
- Supported categories: `admissions`, `fees`, `exams`, `hostel`, `scholarships`, `circulars`, `other`
- Explicit blob metadata keys (`category`, `effective_date`, `version`, `language`, `title`) override path conventions.

## Quickstart (Local Mock Mode)
```bash
cd college-rag-backend
uvicorn app.main:app --reload --port 8000
```
Run tests and offline evaluation:
```bash
pytest
python -m eval.run_eval
```

