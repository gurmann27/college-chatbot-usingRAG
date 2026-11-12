import { useState } from 'react';
import {
  AlertCircle,
  BookOpen,
  Check,
  Copy,
  GraduationCap,
  Info,
  RefreshCw,
  ThumbsDown,
  ThumbsUp,
} from 'lucide-react';
import type { Message } from '../types';
import { cn, formatLanguage } from '../lib/utils';
import MarkdownRenderer from './MarkdownRenderer';
import SourceCitationCard from './SourceCitationCard';

interface Props {
  message: Message;
  canRetry?: boolean;
  onRetry?: () => void;
}

export default function MessageBubble({ message, canRetry, onRetry }: Props) {
  const [openSources, setOpenSources] = useState<Set<number>>(new Set());
  const [copied, setCopied] = useState(false);
  const [feedback, setFeedback] = useState<'up' | 'down' | null>(null);

  const sources = message.sources ?? [];
  const domId = (i: number) => `src-${message.id}-${i + 1}`;
  const langLabel =
    message.language && message.language.toLowerCase() !== 'en'
      ? formatLanguage(message.language)
      : null;

  const toggleSource = (i: number) =>
    setOpenSources((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });

  /** Clicking a [n] badge in the answer opens and scrolls to source n. */
  const handleCitationClick = (n: number) => {
    const i = n - 1;
    if (i < 0 || i >= sources.length) return;
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    setOpenSources((prev) => new Set(prev).add(i));
    requestAnimationFrame(() =>
      document
        .getElementById(domId(i))
        ?.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: 'nearest' }),
    );
  };

  const copyAnswer = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable */
    }
  };

  // ---- User message --------------------------------------------------------
  if (message.role === 'user') {
    return (
      <div className="flex animate-fade-in justify-end">
        <div className="max-w-[85%] whitespace-pre-wrap break-words rounded-[20px] rounded-br-[6px] bg-accent px-4 py-2.5 text-[15px] leading-relaxed text-white shadow-sm sm:max-w-[75%]">
          {message.content}
        </div>
      </div>
    );
  }

  // ---- Assistant message (Content layer: opaque surface, no glass) ---------
  return (
    <div className="flex animate-fade-in gap-3">
      <div
        className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-tone-secondaryTint text-tone-secondary"
        aria-hidden
      >
        <GraduationCap className="h-4 w-4" />
      </div>

      <div className="min-w-0 flex-1">
        <div
          className={cn(
            'rounded-[20px] rounded-tl-[6px] px-4 py-3.5',
            message.error
              ? 'bg-[var(--signal-red-bg)] ring-1 ring-inset ring-[var(--signal-red-ring)]'
              : 'bg-surface shadow-apple ring-1 ring-inset ring-[var(--tone-secondary-ring)]',
          )}
        >
          {message.error ? (
            <div className="flex items-start gap-2.5 text-[14px] text-[var(--signal-red-text)]" role="alert">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
              <div>
                <p className="leading-relaxed">{message.content}</p>
                {canRetry && (
                  <button
                    type="button"
                    onClick={onRetry}
                    className="mt-2.5 inline-flex min-h-[32px] items-center gap-1.5 rounded-lg bg-surface px-3 py-1 text-[13px] font-medium text-[var(--signal-red-text)] shadow-apple transition-colors hover:bg-[var(--bg-hover)]"
                  >
                    <RefreshCw className="h-3.5 w-3.5" aria-hidden />
                    Try Again
                  </button>
                )}
              </div>
            </div>
          ) : (
            <>
              {message.abstained && (
                <div className="mb-2.5 inline-flex items-center gap-1.5 rounded-full bg-[var(--signal-amber-bg)] px-2.5 py-1 text-[12px] font-medium text-[var(--signal-amber-text)] ring-1 ring-inset ring-[var(--signal-amber-ring)]">
                  <Info className="h-3.5 w-3.5 shrink-0" aria-hidden />
                  Not covered in indexed college documents
                </div>
              )}
              <MarkdownRenderer content={message.content} onCitationClick={handleCitationClick} />
            </>
          )}
        </div>

        {!message.error && (
          <div className="mt-1.5 flex flex-wrap items-center gap-1 pl-1">
            <button
              type="button"
              onClick={copyAnswer}
              className="inline-flex min-h-[30px] items-center gap-1.5 rounded-lg px-2 py-1 text-[12px] font-medium text-ink-secondary transition-colors hover:bg-[var(--bg-hover)] hover:text-ink-primary"
            >
              {copied ? <Check className="h-3.5 w-3.5 text-[var(--signal-green-text)]" /> : <Copy className="h-3.5 w-3.5" />}
              {copied ? 'Copied' : 'Copy'}
            </button>

            <div className="flex items-center gap-0.5" role="group" aria-label="Response feedback">
              <button
                type="button"
                onClick={() => setFeedback((f) => (f === 'up' ? null : 'up'))}
                aria-pressed={feedback === 'up'}
                aria-label="Helpful answer"
                title="Helpful"
                className={cn(
                  'flex h-[30px] w-[30px] items-center justify-center rounded-lg transition-colors',
                  feedback === 'up'
                    ? 'bg-accent-tint text-accent-text'
                    : 'text-ink-tertiary hover:bg-[var(--bg-hover)] hover:text-ink-primary',
                )}
              >
                <ThumbsUp className="h-3.5 w-3.5" />
              </button>
              <button
                type="button"
                onClick={() => setFeedback((f) => (f === 'down' ? null : 'down'))}
                aria-pressed={feedback === 'down'}
                aria-label="Not helpful"
                title="Not helpful"
                className={cn(
                  'flex h-[30px] w-[30px] items-center justify-center rounded-lg transition-colors',
                  feedback === 'down'
                    ? 'bg-[var(--signal-amber-bg)] text-[var(--signal-amber-text)]'
                    : 'text-ink-tertiary hover:bg-[var(--bg-hover)] hover:text-ink-primary',
                )}
              >
                <ThumbsDown className="h-3.5 w-3.5" />
              </button>
            </div>

            {langLabel && (
              <span className="ml-auto rounded-full bg-secondary px-2 py-0.5 text-[11px] font-medium text-ink-secondary">
                {langLabel}
              </span>
            )}
          </div>
        )}

        {sources.length > 0 && (
          <section aria-label="Cited sources" className="mt-3">
            <h3 className="mb-2 flex items-center gap-1.5 px-0.5 text-[12px] font-semibold text-tone-secondary">
              <BookOpen className="h-3.5 w-3.5" aria-hidden />
              <span className="tabular-nums">Sources ({sources.length})</span>
            </h3>
            <div className="space-y-2">
              {sources.map((s, i) => (
                <SourceCitationCard
                  key={`${s.id}-${i}`}
                  source={s}
                  index={i + 1}
                  domId={domId(i)}
                  open={openSources.has(i)}
                  onToggle={() => toggleSource(i)}
                />
              ))}
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
