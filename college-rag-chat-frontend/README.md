# College Assistant – RAG Chat Frontend

React + Vite + TypeScript + Tailwind UI for a FastAPI RAG backend.

## Setup

```bash
npm install
cp .env.example .env     # set VITE_API_BASE_URL; keep VITE_USE_MOCK=true to demo without a backend
npm run dev              # http://localhost:5173
npm run build            # type-check + production build into dist/
```

Set `VITE_USE_MOCK=false` to talk to the real backend.

## Structure

```
src/
├── App.tsx                      Layout, drawer/modal state, document filter state
├── main.tsx / index.css         Entry + Tailwind layers
├── types.ts                     Message, SourceChunk, ChatSession, IndexedDocument, API types
├── services/
│   ├── api.ts                   Centralised API client (fetch + XHR upload) and response normalisers
│   └── mock.ts                  In-browser mock backend
├── hooks/
│   ├── useChatStore.ts          Sessions, active chat, send/retry/delete, localStorage cache
│   └── useDocuments.ts          Indexed-document list
├── components/
│   ├── Sidebar.tsx              New chat, grouped history, two-step delete, mobile drawer
│   ├── ChatWindow.tsx           Message list, auto-scroll, typing indicator, empty state
│   ├── ChatInput.tsx            Auto-resizing textarea, document filter dropdown, send
│   ├── MessageBubble.tsx        User/assistant bubbles, copy, error + retry, sources list
│   ├── SourceCitationCard.tsx   Accordion card: document, page, score, snippet
│   ├── MarkdownRenderer.tsx     react-markdown + syntax highlighting + clickable [n] badges
│   └── DocumentPanel.tsx        Modal: drag-and-drop upload with progress + indexed list
└── lib/utils.ts
```

## API contract

| Endpoint | Request | Response |
|---|---|---|
| `POST /api/v1/chat` | `{ query, session_id?, document_ids? }` | `{ session_id, answer, sources: [{ id, document_name, page, score, snippet, validated? }] }` |
| `GET /api/v1/history` | – | `[{ id, title, created_at, updated_at, messages: [{ role, content, sources }] }]` |
| `DELETE /api/v1/history/{id}` | – | `204` (optional; failures are ignored) |
| `GET /api/v1/documents` | – | `[{ id, name, size_bytes, pages, uploaded_at, status }]` |
| `POST /api/v1/upload` | multipart, field `file` | the created document object |

`api.ts` accepts common alternative field names (`filename`, `page_number`, `similarity`,
`rerank_score`, `text`, `citations`, …). Edit the `normalize*` functions if your schema differs.

**Citations:** if the answer text contains `[1]`, `[2]`, … markers, they render as clickable badges that
open and scroll to the matching source card (numbered by order in `sources`).

## Notes

- **CORS:** allow the frontend origin in FastAPI (`CORSMiddleware`).
- **Auth:** `getAuthToken()` in `api.ts` is the hook for an Azure AD / MSAL bearer token.
- **Document filter** sends `document_ids`; make sure the backend applies it as a search filter.
- `/api/v1/documents` and `DELETE /api/v1/history/{id}` go beyond the three endpoints you listed.
  The upload panel needs a way to list indexed documents; remove or rename them if you prefer.
- Chats are cached in `localStorage` and merged with `/history` on load.
