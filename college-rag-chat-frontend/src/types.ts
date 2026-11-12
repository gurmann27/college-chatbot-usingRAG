/** A retrieved chunk that supports (or was used to produce) an answer. */
export interface SourceChunk {
  id: string;
  document_id?: string;
  document_name: string;
  /** 1-based page number, if the chunk came from a paginated document. */
  page?: number | null;
  /** Similarity / rerank score. 0–1 is shown as a percentage, anything else as a decimal. */
  score: number;
  /** Text of the retrieved chunk. */
  snippet: string;
  /** Result of the backend's citation validation step, if it reports one. */
  validated?: boolean;
  category?: string;
  effective_date?: string;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: SourceChunk[];
  createdAt: number;
  /** True when the request failed; rendered as an error bubble with a retry button. */
  error?: boolean;
  /** True when the backend reported that the knowledge base did not contain an answer. */
  abstained?: boolean;
  /** Detected language code returned by the backend (e.g., en, hi, hi-Latn, ta). */
  language?: string;
}

export interface ChatSession {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  messages: Message[];
}

/** POST /api/v1/chat request body */
export interface ChatRequest {
  query: string;
  session_id?: string | null;
  /** Restrict retrieval to these documents. Omit to search everything. */
  document_ids?: string[];
}

/** POST /api/v1/chat response body (after normalisation) */
export interface ChatResponse {
  session_id: string;
  answer: string;
  sources: SourceChunk[];
  message_id?: string;
  language?: string;
  abstained?: boolean;
}

export type DocumentStatus = 'indexed' | 'processing' | 'failed';

export interface IndexedDocument {
  id: string;
  name: string;
  sizeBytes?: number;
  pages?: number;
  uploadedAt: number;
  status: DocumentStatus;
  category?: string;
  effectiveDate?: string;
  version?: string;
  language?: string;
}
