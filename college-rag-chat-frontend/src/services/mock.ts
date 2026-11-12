/**
 * Mock backend used when VITE_USE_MOCK=true, so the UI can be developed
 * and demoed without the FastAPI service running.
 */
import type {
  ChatRequest,
  ChatResponse,
  ChatSession,
  IndexedDocument,
  SourceChunk,
} from '../types';
import { uid } from '../lib/utils';

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

const DAY = 24 * 60 * 60 * 1000;

let mockDocs: IndexedDocument[] = [
  {
    id: 'doc-ds',
    name: 'CSE_Data_Structures_Syllabus_2025.pdf',
    sizeBytes: 412_000,
    pages: 18,
    uploadedAt: Date.now() - 20 * DAY,
    status: 'indexed',
  },
  {
    id: 'doc-os',
    name: 'OS_Lecture_Notes_Unit3.pdf',
    sizeBytes: 1_840_000,
    pages: 42,
    uploadedAt: Date.now() - 9 * DAY,
    status: 'indexed',
  },
  {
    id: 'doc-exam',
    name: 'Exam_Circular_Nov2026.pdf',
    sizeBytes: 98_000,
    pages: 3,
    uploadedAt: Date.now() - 2 * DAY,
    status: 'indexed',
  },
  {
    id: 'doc-fee',
    name: 'Fee_Payment_Notice.txt',
    sizeBytes: 4_200,
    uploadedAt: Date.now() - 1 * DAY,
    status: 'processing',
  },
];

const SOURCE_POOL: SourceChunk[] = [
  {
    id: 'c-101',
    document_id: 'doc-ds',
    document_name: 'CSE_Data_Structures_Syllabus_2025.pdf',
    page: 4,
    score: 0.91,
    validated: true,
    snippet:
      'Unit II – Linear Data Structures: arrays, linked lists (singly, doubly, circular), stacks and queues with applications such as expression evaluation and BFS. Students must implement each structure in C or Python.',
  },
  {
    id: 'c-102',
    document_id: 'doc-os',
    document_name: 'OS_Lecture_Notes_Unit3.pdf',
    page: 17,
    score: 0.78,
    validated: true,
    snippet:
      'A deadlock can arise only if four conditions hold simultaneously: mutual exclusion, hold and wait, no pre-emption and circular wait. Breaking any one of them prevents deadlock.',
  },
  {
    id: 'c-103',
    document_id: 'doc-exam',
    document_name: 'Exam_Circular_Nov2026.pdf',
    page: 1,
    score: 0.64,
    validated: false,
    snippet:
      'End-semester examinations for all UG programmes will commence on 2 December 2026. Hall tickets will be available on the student portal from 24 November 2026.',
  },
];

export async function mockChat(req: ChatRequest): Promise<ChatResponse> {
  await sleep(1400);

  // Respect the document filter, like the real backend would.
  const pool = req.document_ids?.length
    ? SOURCE_POOL.filter((s) => s.document_id && req.document_ids!.includes(s.document_id))
    : SOURCE_POOL;

  if (pool.length === 0) {
    return {
      session_id: req.session_id ?? uid(),
      answer:
        "I couldn't find anything relevant in the selected documents. Try selecting more documents or rephrasing your question.",
      sources: [],
    };
  }

  const answer = [
    `Here's what the documents say about **"${req.query.slice(0, 80)}"**:`,
    '',
    `- The syllabus covers linear data structures such as linked lists, stacks and queues [1].`,
    pool.length > 1
      ? `- Deadlock requires four simultaneous conditions, and removing any one prevents it [2].`
      : '',
    pool.length > 2
      ? `- Exams start on **2 December 2026**; hall tickets open on 24 November [3].`
      : '',
    '',
    'A minimal stack in Python, as expected in the lab:',
    '',
    '```python',
    'class Stack:',
    '    def __init__(self):',
    '        self._items = []',
    '',
    '    def push(self, x):',
    '        self._items.append(x)',
    '',
    '    def pop(self):',
    '        return self._items.pop()',
    '```',
  ]
    .filter((l, i, arr) => !(l === '' && arr[i - 1] === ''))
    .join('\n');

  return { session_id: req.session_id ?? uid(), answer, sources: pool, message_id: uid() };
}

export async function mockHistory(): Promise<ChatSession[]> {
  await sleep(300);
  return [];
}

export async function mockListDocuments(): Promise<IndexedDocument[]> {
  await sleep(300);
  return [...mockDocs];
}

export async function mockUpload(
  file: File,
  onProgress?: (pct: number) => void,
): Promise<IndexedDocument> {
  for (let p = 0; p <= 100; p += 20) {
    onProgress?.(p);
    await sleep(180);
  }
  const doc: IndexedDocument = {
    id: uid(),
    name: file.name,
    sizeBytes: file.size,
    uploadedAt: Date.now(),
    status: 'processing',
  };
  mockDocs = [doc, ...mockDocs];
  return doc;
}
