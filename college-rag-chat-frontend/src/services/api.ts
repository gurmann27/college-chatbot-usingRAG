/**
 * Centralised API client for the FastAPI backend.
 *
 *  - Base URL comes from VITE_API_BASE_URL.
 *  - Set VITE_USE_MOCK=true to use the in-browser mock instead of the network.
 *  - Responses are normalised so small naming differences in the backend
 *    (e.g. `filename` vs `document_name`, `page_number` vs `page`) don't
 *    break the UI. Adjust the `normalize*` helpers if your schema differs.
 *
 * Endpoints
 *   POST   /api/v1/chat           -> { session_id, answer, sources[] }
 *   GET    /api/v1/history        -> sessions[] (or { sessions: [] })
 *   DELETE /api/v1/history/{id}   -> 204 (best effort)
 *   GET    /api/v1/documents      -> documents[] (or { documents: [] })
 *   POST   /api/v1/upload         -> multipart/form-data, field "file"
 */
import type {
  ChatRequest,
  ChatResponse,
  ChatSession,
  IndexedDocument,
  Message,
  SourceChunk,
} from '../types';
import { mockChat, mockHistory, mockListDocuments, mockUpload } from './mock';

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000').replace(
  /\/$/,
  '',
);
export const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true';

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

/**
 * Hook for authentication. Replace with your Azure AD / MSAL token lookup,
 * or return null if the API is open.
 */
function getAuthToken(): string | null {
  try {
    return localStorage.getItem('auth_token');
  } catch {
    return null;
  }
}

function getClientId(): string {
  const key = 'rag_client_id';
  try {
    let cid = localStorage.getItem(key);
    if (!cid) {
      cid = typeof crypto !== 'undefined' && 'randomUUID' in crypto
        ? crypto.randomUUID()
        : `client-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
      localStorage.setItem(key, cid);
    }
    return cid;
  } catch {
    return 'anonymous-browser';
  }
}

// ---------------------------------------------------------------------------
// Generic JSON request helper (timeout, error parsing, auth header)
// ---------------------------------------------------------------------------
async function request<T>(
  path: string,
  init: RequestInit & { timeoutMs?: number } = {},
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), init.timeoutMs ?? 60_000);

  try {
    const headers = new Headers(init.headers);
    if (init.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json');
    }
    const token = getAuthToken();
    if (token) headers.set('Authorization', `Bearer ${token}`);
    if (!headers.has('X-Client-Id')) {
      headers.set('X-Client-Id', getClientId());
    }

    const res = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers,
      signal: init.signal ?? controller.signal,
    });

    if (!res.ok) {
      let detail = res.statusText || `Request failed (${res.status})`;
      try {
        const body = await res.json();
        // FastAPI errors look like { "detail": "..." } or { "detail": [ {...} ] }
        detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail ?? body);
      } catch {
        /* body wasn't JSON – keep statusText */
      }
      throw new ApiError(detail, res.status);
    }

    if (res.status === 204) return undefined as T;
    return (await res.json()) as T;
  } catch (e) {
    if (e instanceof ApiError) throw e;
    if (e instanceof DOMException && e.name === 'AbortError') {
      throw new ApiError('The request timed out. Please try again.', 408);
    }
    throw new ApiError('Cannot reach the server. Check your connection and try again.', 0);
  } finally {
    clearTimeout(timer);
  }
}

// ---------------------------------------------------------------------------
// Normalisers – map whatever the backend sends to our front-end types
// ---------------------------------------------------------------------------
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Raw = Record<string, any>;

const toMs = (v: unknown): number => {
  const t = typeof v === 'string' || typeof v === 'number' ? Date.parse(String(v)) : NaN;
  return Number.isNaN(t) ? Date.now() : t;
};

function normalizeSource(raw: Raw, i: number): SourceChunk {
  const score = Number(raw.score ?? raw.similarity ?? raw.rerank_score ?? raw.reranker_score ?? 0);
  return {
    id: String(raw.id ?? raw.chunk_id ?? `chunk-${i}`),
    document_id: raw.document_id ?? undefined,
    document_name: String(raw.document_name ?? raw.filename ?? raw.source ?? 'Unknown document'),
    page: raw.page ?? raw.page_number ?? null,
    score: Number.isFinite(score) ? score : 0,
    snippet: String(raw.snippet ?? raw.text ?? raw.content ?? ''),
    validated: typeof raw.validated === 'boolean' ? raw.validated : undefined,
    category: typeof raw.category === 'string' ? raw.category : undefined,
    effective_date: typeof raw.effective_date === 'string' ? raw.effective_date : undefined,
  };
}

function normalizeChat(raw: Raw, fallbackSessionId?: string | null): ChatResponse {
  const sources: Raw[] = raw.sources ?? raw.citations ?? [];
  return {
    session_id: String(raw.session_id ?? fallbackSessionId ?? ''),
    answer: String(raw.answer ?? raw.response ?? ''),
    sources: sources.map(normalizeSource),
    message_id: raw.message_id ? String(raw.message_id) : undefined,
    language: typeof raw.language === 'string' ? raw.language : undefined,
    abstained: typeof raw.abstained === 'boolean' ? raw.abstained : undefined,
  };
}

function normalizeSession(raw: Raw): ChatSession {
  const id = String(raw.id ?? raw.session_id);
  const messages: Message[] = (raw.messages ?? []).map((m: Raw, i: number) => ({
    id: String(m.id ?? `${id}-${i}`),
    role: m.role === 'user' ? 'user' : 'assistant',
    content: String(m.content ?? ''),
    sources: (m.sources ?? []).map(normalizeSource),
    createdAt: toMs(m.created_at),
  }));
  return {
    id,
    title: String(raw.title ?? 'Untitled chat'),
    createdAt: toMs(raw.created_at),
    updatedAt: toMs(raw.updated_at ?? raw.created_at),
    messages,
  };
}

function normalizeDocument(input: Raw): IndexedDocument {
  const raw: Raw = input.document ?? input;
  return {
    id: String(raw.id ?? raw.document_id ?? raw.filename ?? raw.name),
    name: String(raw.name ?? raw.filename ?? 'Untitled'),
    sizeBytes: raw.size_bytes ?? raw.size ?? undefined,
    pages: raw.pages ?? raw.page_count ?? undefined,
    uploadedAt: toMs(raw.uploaded_at ?? raw.created_at),
    status: raw.status === 'processing' || raw.status === 'failed' ? raw.status : 'indexed',
    category: typeof raw.category === 'string' ? raw.category : undefined,
    effectiveDate: typeof raw.effective_date === 'string' ? raw.effective_date : undefined,
    version: typeof raw.version === 'string' ? raw.version : undefined,
    language: typeof raw.language === 'string' ? raw.language : undefined,
  };
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/** POST /api/v1/chat – send a question, receive an answer plus source chunks. */
export async function sendChat(req: ChatRequest): Promise<ChatResponse> {
  if (USE_MOCK) return mockChat(req);
  const raw = await request<Raw>('/api/v1/chat', {
    method: 'POST',
    body: JSON.stringify(req),
    timeoutMs: 90_000, // hybrid search + rerank + LLM can be slow
  });
  return normalizeChat(raw, req.session_id);
}

/** GET /api/v1/history – past chat sessions. */
export async function getHistory(): Promise<ChatSession[]> {
  if (USE_MOCK) return mockHistory();
  const raw = await request<Raw[] | { sessions: Raw[] }>('/api/v1/history');
  const list = Array.isArray(raw) ? raw : raw.sessions ?? [];
  return list.map(normalizeSession);
}

/** DELETE /api/v1/history/{id} – remove a session server-side (best effort). */
export async function deleteSession(id: string): Promise<void> {
  if (USE_MOCK) return;
  await request<void>(`/api/v1/history/${encodeURIComponent(id)}`, { method: 'DELETE' });
}

/** GET /api/v1/documents – documents currently indexed. */
export async function listDocuments(): Promise<IndexedDocument[]> {
  if (USE_MOCK) return mockListDocuments();
  const raw = await request<Raw[] | { documents: Raw[] }>('/api/v1/documents');
  const list = Array.isArray(raw) ? raw : raw.documents ?? [];
  return list.map(normalizeDocument);
}

/**
 * POST /api/v1/upload – multipart upload (field name "file").
 * Uses XMLHttpRequest because fetch() can't report upload progress.
 */
export function uploadDocument(
  file: File,
  onProgress?: (percent: number) => void,
): Promise<IndexedDocument> {
  if (USE_MOCK) return mockUpload(file, onProgress);

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', `${API_BASE_URL}/api/v1/upload`);

    const token = getAuthToken();
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`);

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress?.(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onerror = () => reject(new ApiError('Network error during upload.', 0));
    xhr.ontimeout = () => reject(new ApiError('The upload timed out.', 408));
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(normalizeDocument(JSON.parse(xhr.responseText)));
        } catch {
          reject(new ApiError('Unexpected response from the server.', xhr.status));
        }
        return;
      }
      let detail: string = xhr.statusText || 'Upload failed';
      try {
        const body = JSON.parse(xhr.responseText);
        if (typeof body.detail === 'string') detail = body.detail;
      } catch {
        /* keep statusText */
      }
      reject(new ApiError(detail, xhr.status));
    };

    const formData = new FormData();
    formData.append('file', file);
    xhr.send(formData);
  });
}