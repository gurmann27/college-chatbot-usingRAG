import { useEffect, useMemo, useRef, useState, type DragEvent } from 'react';
import {
  AlertCircle,
  CheckCircle2,
  FileText,
  Info,
  Loader2,
  RefreshCw,
  Search,
  Upload,
  X,
} from 'lucide-react';
import type { DocumentStatus, IndexedDocument } from '../types';
import { USE_MOCK, uploadDocument } from '../services/api';
import { cn, formatBytes, formatCategory, formatDate, formatLanguage, uid } from '../lib/utils';

interface Props {
  open: boolean;
  onClose: () => void;
  documents: IndexedDocument[];
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
}

const ALLOWED_EXTENSIONS = ['.pdf', '.txt', '.md', '.docx'];
const MAX_SIZE_MB = 25;

interface UploadItem {
  id: string;
  name: string;
  progress: number;
  status: 'uploading' | 'done' | 'error';
  error?: string;
}

const STATUS_STYLE: Record<DocumentStatus, { label: string; className: string }> = {
  indexed: {
    label: 'Indexed',
    className:
      'bg-[var(--signal-green-bg)] text-[var(--signal-green-text)] ring-[var(--signal-green-ring)]',
  },
  processing: {
    label: 'Processing',
    className:
      'bg-[var(--signal-amber-bg)] text-[var(--signal-amber-text)] ring-[var(--signal-amber-ring)]',
  },
  failed: {
    label: 'Failed',
    className:
      'bg-[var(--signal-red-bg)] text-[var(--signal-red-text)] ring-[var(--signal-red-ring)]',
  },
};

export default function DocumentPanel({
  open,
  onClose,
  documents,
  loading,
  error,
  onRefresh,
}: Props) {
  const [uploads, setUploads] = useState<UploadItem[]>([]);
  const [dragging, setDragging] = useState(false);
  const [query, setQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');

  const inputRef = useRef<HTMLInputElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeBtnRef = useRef<HTMLButtonElement>(null);
  const lastFocusedRef = useRef<HTMLElement | null>(null);

  // Move focus into the sheet on open, trap Tab navigation, and restore focus on close.
  useEffect(() => {
    if (!open) return;
    lastFocusedRef.current = document.activeElement as HTMLElement | null;
    closeBtnRef.current?.focus();

    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
        return;
      }
      if (e.key === 'Tab' && dialogRef.current) {
        const focusables = dialogRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
        );
        if (focusables.length === 0) return;
        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
      lastFocusedRef.current?.focus();
    };
  }, [open, onClose]);

  const categories = useMemo(() => {
    const set = new Set<string>();
    for (const d of documents) {
      if (d.category) set.add(d.category.toLowerCase());
    }
    return Array.from(set).sort();
  }, [documents]);

  const filteredDocs = useMemo(() => {
    const q = query.trim().toLowerCase();
    return documents.filter((d) => {
      if (selectedCategory !== 'all' && d.category?.toLowerCase() !== selectedCategory) return false;
      if (!q) return true;
      return (
        d.name.toLowerCase().includes(q) ||
        (d.category?.toLowerCase().includes(q) ?? false) ||
        (d.effectiveDate?.toLowerCase().includes(q) ?? false)
      );
    });
  }, [documents, query, selectedCategory]);

  if (!open) return null;

  const patch = (id: string, change: Partial<UploadItem>) =>
    setUploads((prev) => prev.map((u) => (u.id === id ? { ...u, ...change } : u)));

  const handleFiles = (files: FileList | File[]) => {
    for (const file of Array.from(files)) {
      const id = uid();
      const ext = `.${file.name.split('.').pop()?.toLowerCase() ?? ''}`;

      if (!ALLOWED_EXTENSIONS.includes(ext)) {
        setUploads((p) => [
          {
            id,
            name: file.name,
            progress: 0,
            status: 'error',
            error: `Unsupported type (${ALLOWED_EXTENSIONS.join(', ')})`,
          },
          ...p,
        ]);
        continue;
      }
      if (file.size > MAX_SIZE_MB * 1024 * 1024) {
        setUploads((p) => [
          { id, name: file.name, progress: 0, status: 'error', error: `Larger than ${MAX_SIZE_MB} MB` },
          ...p,
        ]);
        continue;
      }

      setUploads((p) => [{ id, name: file.name, progress: 0, status: 'uploading' }, ...p]);
      uploadDocument(file, (progress) => patch(id, { progress }))
        .then(() => {
          patch(id, { progress: 100, status: 'done' });
          onRefresh();
        })
        .catch((e: unknown) =>
          patch(id, { status: 'error', error: e instanceof Error ? e.message : 'Upload failed' }),
        );
    }
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    handleFiles(e.dataTransfer.files);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-[var(--scrim)] p-3 sm:p-4"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="docs-title"
        className="flex max-h-[86vh] w-full max-w-2xl flex-col overflow-hidden rounded-[22px] bg-surface shadow-sheet"
      >
        {/* Sheet Header */}
        <header className="flex items-center justify-between border-b border-separator px-5 py-4">
          <div>
            <h2 id="docs-title" className="text-[17px] font-semibold tracking-[-0.015em] text-ink-primary">
              Knowledge Base
            </h2>
            <p className="mt-0.5 text-[13px] text-ink-secondary">
              Official college circulars and guidelines indexed for citation.
            </p>
          </div>
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={onRefresh}
              disabled={loading}
              aria-label="Refresh Documents"
              title="Refresh"
              className="flex h-10 w-10 items-center justify-center rounded-xl text-ink-secondary transition-colors hover:bg-[var(--bg-hover)] hover:text-ink-primary disabled:opacity-50 md:h-8 md:w-8 md:rounded-lg"
            >
              <RefreshCw className={cn('h-4 w-4', loading && 'animate-spin')} />
            </button>
            <button
              ref={closeBtnRef}
              type="button"
              onClick={onClose}
              aria-label="Done"
              className="flex h-10 w-10 items-center justify-center rounded-xl text-ink-secondary transition-colors hover:bg-[var(--bg-hover)] hover:text-ink-primary md:h-8 md:w-8 md:rounded-lg"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4 scrollbar-thin">
          {/* Upload dropzone only when running with the mock client */}
          {USE_MOCK ? (
            <label
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={onDrop}
              className={cn(
                'mb-5 flex cursor-pointer flex-col items-center gap-1 rounded-2xl border-2 border-dashed px-4 py-6 text-center transition-colors',
                dragging
                  ? 'border-[var(--accent-text)] bg-accent-tint'
                  : 'border-separator hover:bg-[var(--bg-hover)]',
              )}
            >
              <Upload className="h-6 w-6 text-accent-text" aria-hidden />
              <span className="text-[14px] font-medium text-ink-primary">
                Drop files here or click to browse
              </span>
              <span className="text-[12px] text-ink-secondary">
                PDF, TXT, MD, or DOCX · up to {MAX_SIZE_MB} MB each
              </span>
              <input
                ref={inputRef}
                type="file"
                multiple
                accept={ALLOWED_EXTENSIONS.join(',')}
                className="sr-only"
                onChange={(e) => {
                  if (e.target.files) handleFiles(e.target.files);
                  e.target.value = '';
                }}
              />
            </label>
          ) : (
            <div className="mb-4 flex items-start gap-2.5 rounded-xl bg-canvas px-3.5 py-2.5 text-[13px] text-ink-secondary">
              <Info className="mt-0.5 h-4 w-4 shrink-0 text-tone-secondary" aria-hidden />
              <span>
                Documents are synced centrally from the college repository. Use the scope filter in
                the composer to narrow questions to specific files.
              </span>
            </div>
          )}

          {uploads.length > 0 && (
            <ul className="mb-5 space-y-2" aria-label="Uploads">
              {uploads.map((u) => (
                <li key={u.id} className="rounded-xl bg-canvas px-3.5 py-2.5">
                  <div className="flex items-center gap-2 text-[13px]">
                    {u.status === 'uploading' && (
                      <Loader2 className="h-4 w-4 animate-spin text-accent-text" />
                    )}
                    {u.status === 'done' && (
                      <CheckCircle2 className="h-4 w-4 text-[var(--signal-green-text)]" />
                    )}
                    {u.status === 'error' && (
                      <AlertCircle className="h-4 w-4 text-[var(--signal-red-text)]" />
                    )}
                    <span className="min-w-0 flex-1 truncate font-medium text-ink-primary">
                      {u.name}
                    </span>
                    <span className="text-[12px] tabular-nums text-ink-secondary">
                      {u.status === 'uploading' && `${u.progress}%`}
                      {u.status === 'done' && 'Uploaded'}
                    </span>
                  </div>
                  {u.status === 'uploading' && (
                    <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-secondary">
                      <div
                        className="h-full rounded-full bg-accent transition-all"
                        style={{ width: `${u.progress}%` }}
                      />
                    </div>
                  )}
                  {u.status === 'error' && (
                    <p className="mt-1 text-[12px] text-[var(--signal-red-text)]">{u.error}</p>
                  )}
                </li>
              ))}
            </ul>
          )}

          {/* Search Field & Category Filter Pills */}
          <div className="mb-3 space-y-2.5">
            <div className="relative flex items-center">
              <Search className="pointer-events-none absolute left-3 h-4 w-4 text-ink-tertiary" aria-hidden />
              <input
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search indexed documents…"
                aria-label="Search indexed documents"
                className="h-10 w-full rounded-xl bg-canvas pl-9 pr-9 text-[14px] text-ink-primary placeholder:text-ink-tertiary ring-1 ring-inset ring-separator focus:ring-2 focus:ring-[var(--accent-text)] md:h-9"
              />
              {query && (
                <button
                  type="button"
                  onClick={() => setQuery('')}
                  aria-label="Clear search"
                  className="absolute right-1.5 flex h-8 w-8 items-center justify-center rounded-lg text-ink-tertiary hover:bg-[var(--bg-hover)] hover:text-ink-primary md:h-7 md:w-7"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              )}
            </div>

            {categories.length > 0 && (
              <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter by category">
                <button
                  type="button"
                  onClick={() => setSelectedCategory('all')}
                  aria-pressed={selectedCategory === 'all'}
                  className={cn(
                    'min-h-[30px] rounded-full px-3 py-1 text-[12px] font-medium transition-colors',
                    selectedCategory === 'all'
                      ? 'bg-accent text-white'
                      : 'bg-canvas text-ink-secondary hover:bg-[var(--bg-hover)] hover:text-ink-primary',
                  )}
                >
                  All ({documents.length})
                </button>
                {categories.map((cat) => (
                  <button
                    key={cat}
                    type="button"
                    onClick={() => setSelectedCategory(cat)}
                    aria-pressed={selectedCategory === cat}
                    className={cn(
                      'min-h-[30px] rounded-full px-3 py-1 text-[12px] font-medium transition-colors',
                      selectedCategory === cat
                        ? 'bg-accent text-white'
                        : 'bg-canvas text-ink-secondary hover:bg-[var(--bg-hover)] hover:text-ink-primary',
                    )}
                  >
                    {formatCategory(cat)}
                  </button>
                ))}
              </div>
            )}
          </div>

          {error && (
            <p
              className="mb-3 rounded-xl bg-[var(--signal-red-bg)] px-3.5 py-2.5 text-[13px] text-[var(--signal-red-text)]"
              role="alert"
            >
              {error}
            </p>
          )}

          {!error && !loading && filteredDocs.length === 0 && (
            <p className="py-8 text-center text-[14px] text-ink-secondary">
              {documents.length === 0
                ? 'No documents have been indexed yet.'
                : 'No documents match your filter.'}
            </p>
          )}

          <ul className="divide-y divide-separator rounded-2xl bg-canvas px-3.5">
            {filteredDocs.map((d) => {
              const status = STATUS_STYLE[d.status];
              const meta = [
                d.category ? formatCategory(d.category) : null,
                d.version ? `v${d.version}` : null,
                d.pages ? `${d.pages} ${d.pages === 1 ? 'page' : 'pages'}` : null,
                formatBytes(d.sizeBytes) || null,
                d.language ? formatLanguage(d.language) : null,
                d.effectiveDate ? `Effective ${d.effectiveDate}` : formatDate(d.uploadedAt),
              ]
                .filter(Boolean)
                .join(' · ');

              return (
                <li key={d.id} className="flex items-center gap-3 py-3">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-surface shadow-apple">
                    <FileText className="h-4 w-4 text-tone-secondary" aria-hidden />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[14px] font-medium text-ink-primary" title={d.name}>
                      {d.name}
                    </p>
                    <p className="mt-0.5 truncate text-[12px] tabular-nums text-ink-secondary">
                      {meta}
                    </p>
                  </div>
                  <span
                    className={cn(
                      'shrink-0 rounded-full px-2.5 py-0.5 text-[11px] font-semibold ring-1 ring-inset',
                      status.className,
                    )}
                  >
                    {status.label}
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      </div>
    </div>
  );
}
