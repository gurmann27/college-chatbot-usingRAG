import { useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent } from 'react';
import { ArrowUp, Check, ChevronDown, FileText, Paperclip } from 'lucide-react';
import type { IndexedDocument } from '../types';
import { cn } from '../lib/utils';

interface Props {
  onSend: (text: string) => void;
  disabled?: boolean;
  documents: IndexedDocument[];
  selectedDocIds: string[];
  onChangeSelected: (ids: string[]) => void;
}

const MAX_HEIGHT = 180;

export default function ChatInput({
  onSend,
  disabled,
  documents,
  selectedDocIds,
  onChangeSelected,
}: Props) {
  const [text, setText] = useState('');
  const [filterOpen, setFilterOpen] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const filterRef = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, MAX_HEIGHT)}px`;
  }, [text]);

  useEffect(() => {
    if (!filterOpen) return;
    const onDown = (e: MouseEvent) => {
      if (!filterRef.current?.contains(e.target as Node)) setFilterOpen(false);
    };
    const onKey = (e: globalThis.KeyboardEvent) => e.key === 'Escape' && setFilterOpen(false);
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [filterOpen]);

  const canSend = text.trim().length > 0 && !disabled;

  const submit = () => {
    if (!canSend) return;
    onSend(text);
    setText('');
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  };

  const toggleDoc = (id: string) =>
    onChangeSelected(
      selectedDocIds.includes(id) ? selectedDocIds.filter((d) => d !== id) : [...selectedDocIds, id],
    );

  const filterLabel =
    selectedDocIds.length === 0
      ? 'All Documents'
      : `${selectedDocIds.length} Document${selectedDocIds.length > 1 ? 's' : ''}`;

  return (
    <div className="pointer-events-none absolute inset-x-0 bottom-0 z-20 px-3 pb-3 pt-6 sm:px-5 sm:pb-4">
      <div className="scroll-edge-bottom pointer-events-none absolute inset-x-0 bottom-0 -z-10 h-40" aria-hidden />

      <div className="pointer-events-auto mx-auto max-w-3xl">
        <div className="liquid-glass rounded-[22px] transition-shadow focus-within:ring-2 focus-within:ring-[var(--accent-text)]">
          <textarea
            ref={textareaRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={onKeyDown}
            rows={1}
            placeholder="Ask in English, हिन्दी, Hinglish, or தமிழ்…"
            aria-label="Ask a question"
            className="block w-full resize-none bg-transparent px-4 pb-1.5 pt-3.5 text-[15px] leading-relaxed text-ink-primary placeholder:text-ink-tertiary focus:outline-none focus-visible:ring-0"
            style={{ maxHeight: MAX_HEIGHT }}
          />

          <div className="flex items-center justify-between gap-2 px-2.5 pb-2.5">
            {/* Document scope filter */}
            <div className="relative" ref={filterRef}>
              <button
                type="button"
                onClick={() => setFilterOpen((o) => !o)}
                aria-haspopup="listbox"
                aria-expanded={filterOpen}
                className={cn(
                  'inline-flex min-h-[36px] items-center gap-1.5 rounded-xl px-2.5 py-1.5 text-[13px] font-medium transition-colors hover:bg-[var(--bg-hover)] md:min-h-[32px]',
                  selectedDocIds.length
                    ? 'bg-tone-secondaryTint text-tone-secondary'
                    : 'text-ink-secondary',
                )}
              >
                <Paperclip className="h-3.5 w-3.5 shrink-0" aria-hidden />
                <span className="tabular-nums">{filterLabel}</span>
                <ChevronDown
                  className={cn('h-3.5 w-3.5 transition-transform', filterOpen && 'rotate-180')}
                  aria-hidden
                />
              </button>

              {filterOpen && (
                <div className="absolute bottom-full left-0 z-30 mb-2 w-80 max-w-[calc(100vw-2rem)] rounded-2xl bg-surface p-2 shadow-sheet ring-1 ring-separator">
                  <div className="flex items-center justify-between px-2 py-1.5">
                    <span className="text-[12px] font-semibold text-ink-secondary">
                      Search Scope
                    </span>
                    {selectedDocIds.length > 0 && (
                      <button
                        type="button"
                        onClick={() => onChangeSelected([])}
                        className="min-h-[28px] rounded-md px-2 py-1 text-[12px] font-medium text-accent-text hover:bg-accent-tint"
                      >
                        Clear Filter
                      </button>
                    )}
                  </div>
                  <ul
                    role="listbox"
                    aria-multiselectable
                    aria-label="Filter documents"
                    className="max-h-60 space-y-0.5 overflow-y-auto scrollbar-thin"
                  >
                    {documents.length === 0 && (
                      <li className="px-2 py-4 text-center text-[13px] text-ink-tertiary">
                        No documents indexed yet.
                      </li>
                    )}
                    {documents.map((d) => {
                      const checked = selectedDocIds.includes(d.id);
                      return (
                        <li key={d.id}>
                          <button
                            type="button"
                            role="option"
                            aria-selected={checked}
                            onClick={() => toggleDoc(d.id)}
                            className={cn(
                              'flex min-h-[38px] w-full items-center gap-2.5 rounded-xl px-2.5 py-1.5 text-left text-[13px] transition-colors',
                              checked
                                ? 'bg-accent-tint font-medium text-accent-text'
                                : 'text-ink-primary hover:bg-[var(--bg-hover)]',
                            )}
                          >
                            <span
                              className={cn(
                                'flex h-4 w-4 shrink-0 items-center justify-center rounded border transition-colors',
                                checked
                                  ? 'border-transparent bg-accent text-white'
                                  : 'border-separator bg-surface',
                              )}
                              aria-hidden
                            >
                              {checked && <Check className="h-3 w-3" strokeWidth={2.5} />}
                            </span>
                            <FileText className="h-4 w-4 shrink-0 text-ink-tertiary" aria-hidden />
                            <span className="truncate" title={d.name}>
                              {d.name}
                            </span>
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              )}
            </div>

            {/* Single prominent primary action */}
            <button
              type="button"
              onClick={submit}
              disabled={!canSend}
              aria-label="Send Message"
              title="Send (Enter)"
              className={cn(
                'flex h-10 w-10 shrink-0 items-center justify-center rounded-full transition-all md:h-9 md:w-9',
                canSend
                  ? 'bg-accent text-white shadow-sm hover:bg-accent-hover active:scale-95'
                  : 'cursor-not-allowed bg-secondary text-ink-tertiary',
              )}
            >
              <ArrowUp className="h-[18px] w-[18px]" strokeWidth={2.25} />
            </button>
          </div>
        </div>

        <p className="mt-2 text-center text-[12px] text-ink-tertiary">
          Answers cite official college documents and may contain errors. Verify details in the
          sources below.
        </p>
      </div>
    </div>
  );
}
