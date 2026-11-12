import { ChevronDown, FileText, ShieldCheck } from 'lucide-react';
import type { SourceChunk } from '../types';
import { cn, formatCategory, formatScore, scoreTone } from '../lib/utils';

interface Props {
  source: SourceChunk;
  index: number;
  domId: string;
  open: boolean;
  onToggle: () => void;
}

export default function SourceCitationCard({ source, index, domId, open, onToggle }: Props) {
  const panelId = `${domId}-panel`;
  const barWidth = source.score >= 0 && source.score <= 1 ? Math.round(source.score * 100) : null;
  const category = formatCategory(source.category);

  return (
    <div
      id={domId}
      className={cn(
        'scroll-mt-20 scroll-mb-44 overflow-hidden rounded-2xl bg-surface transition-shadow',
        open ? 'ring-1 ring-[var(--accent-text)] shadow-apple' : 'shadow-apple',
      )}
    >
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        aria-controls={panelId}
        className="flex min-h-[44px] w-full items-start gap-3 px-3.5 py-3 text-left transition-colors hover:bg-[var(--bg-hover)]"
      >
        <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-tone-secondaryTint text-[11px] font-semibold tabular-nums text-tone-secondary">
          {index}
        </span>

        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <FileText className="h-3.5 w-3.5 shrink-0 text-ink-tertiary" aria-hidden />
            <span
              className="truncate text-[14px] font-medium text-ink-primary"
              title={source.document_name}
            >
              {source.document_name}
            </span>
            {category && (
              <span className="rounded-md bg-secondary px-1.5 py-0.5 text-[11px] font-medium text-ink-secondary">
                {category}
              </span>
            )}
            {source.page != null && (
              <span className="rounded-md bg-secondary px-1.5 py-0.5 text-[11px] font-medium tabular-nums text-ink-secondary">
                p. {source.page}
              </span>
            )}
            <span
              className={cn(
                'rounded-full px-2 py-0.5 text-[11px] font-medium tabular-nums ring-1 ring-inset',
                scoreTone(source.score),
              )}
              title="Relevance score"
            >
              {formatScore(source.score)} match
            </span>
            {source.validated && (
              <span
                className="inline-flex items-center gap-0.5 text-[11px] font-semibold text-[var(--signal-green-text)]"
                title="Citation verified against the answer"
              >
                <ShieldCheck className="h-3.5 w-3.5" aria-hidden />
                Verified
              </span>
            )}
          </span>

          {!open && source.snippet && (
            <span className="mt-1 line-clamp-2 block text-[13px] leading-snug text-ink-secondary">
              {source.snippet}
            </span>
          )}
        </span>

        <ChevronDown
          className={cn(
            'mt-1 h-4 w-4 shrink-0 text-ink-tertiary transition-transform duration-150',
            open && 'rotate-180',
          )}
          aria-hidden
        />
      </button>

      {open && (
        <div id={panelId} className="border-t border-separator bg-canvas/60 px-3.5 py-3">
          {source.effective_date && (
            <p className="mb-2 text-[12px] font-medium text-ink-tertiary">
              Effective date: <span className="tabular-nums text-ink-secondary">{source.effective_date}</span>
            </p>
          )}
          {barWidth !== null && (
            <div className="mb-2.5 h-1 overflow-hidden rounded-full bg-secondary" aria-hidden>
              <div
                className="h-full rounded-full bg-[var(--tone-secondary-text)]"
                style={{ width: `${barWidth}%` }}
              />
            </div>
          )}
          <p className="whitespace-pre-wrap text-[13px] leading-relaxed text-ink-primary">
            {source.snippet || 'No preview available for this chunk.'}
          </p>
        </div>
      )}
    </div>
  );
}
