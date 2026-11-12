import { useEffect, useRef } from 'react';
import { BookMarked, CalendarDays, GraduationCap, Landmark, ShieldCheck, Wallet } from 'lucide-react';
import type { IndexedDocument, Message } from '../types';
import MessageBubble from './MessageBubble';
import ChatInput from './ChatInput';

interface Props {
  messages: Message[];
  isPending: boolean;
  busy: boolean;
  onSend: (text: string) => void;
  onRetry: () => void;
  documents: IndexedDocument[];
  selectedDocIds: string[];
  onChangeSelectedDocs: (ids: string[]) => void;
  onOpenDocuments: () => void;
}

const SUGGESTIONS = [
  {
    icon: Landmark,
    tag: 'Hostel · हिन्दी',
    text: 'हॉस्टल में रात को वापस आने का समय क्या है?',
  },
  {
    icon: Wallet,
    tag: 'Fees · Hinglish',
    text: 'B.Tech ki annual tuition fee kitni hai?',
  },
  {
    icon: CalendarDays,
    tag: 'Exams · English',
    text: 'What is the minimum attendance required to appear in end-semester exams?',
  },
  {
    icon: ShieldCheck,
    tag: 'Scholarships · English',
    text: 'What is the CGPA required for the Institute Merit Scholarship?',
  },
];

function TypingIndicator() {
  return (
    <div className="flex animate-fade-in gap-3" role="status" aria-live="polite">
      <div
        className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-tone-secondaryTint text-tone-secondary"
        aria-hidden
      >
        <GraduationCap className="h-4 w-4" />
      </div>
      <div className="flex items-center gap-2.5 rounded-[20px] rounded-tl-[6px] bg-surface px-4 py-3 shadow-apple">
        <span className="flex gap-1" aria-hidden>
          {[0, 150, 300].map((delay) => (
            <span
              key={delay}
              className="h-1.5 w-1.5 animate-pulse rounded-full bg-tone-secondary"
              style={{ animationDelay: `${delay}ms` }}
            />
          ))}
        </span>
        <span className="text-[14px] text-ink-secondary">
          Searching college documents and verifying citations…
        </span>
      </div>
    </div>
  );
}

function EmptyState({
  onPick,
  docCount,
  onOpenDocuments,
}: {
  onPick: (text: string) => void;
  docCount: number;
  onOpenDocuments: () => void;
}) {
  return (
    <div className="mx-auto flex min-h-full max-w-2xl flex-col items-center justify-center px-4 pb-44 pt-24 text-center">
      <div
        className="brand-duotone mb-5 flex h-14 w-14 items-center justify-center rounded-[18px] text-white shadow-apple"
        aria-hidden
      >
        <GraduationCap className="h-7 w-7" />
      </div>

      <h2 className="text-[26px] font-semibold leading-tight tracking-[-0.022em] text-ink-primary sm:text-[30px]">
        Ask about campus policies
      </h2>
      <p className="mt-2.5 max-w-lg text-[15px] leading-relaxed text-ink-secondary">
        Answers are drawn exclusively from official circulars, hostel rules, fee schedules, and
        exam guidelines—with source citations in English, हिन्दी, Hinglish, or தமிழ்.
      </p>

      {docCount > 0 && (
        <button
          type="button"
          onClick={onOpenDocuments}
          className="mt-4 inline-flex min-h-[36px] items-center gap-1.5 rounded-full bg-surface px-3.5 py-1.5 text-[13px] font-medium text-ink-primary shadow-apple transition-colors hover:bg-[var(--bg-hover)]"
        >
          <BookMarked className="h-3.5 w-3.5 text-tone-secondary" aria-hidden />
          <span className="tabular-nums text-accent-text">Browse {docCount} Indexed Documents…</span>
        </button>
      )}

      <div className="mt-7 grid w-full gap-2.5 sm:grid-cols-2">
        {SUGGESTIONS.map(({ icon: Icon, tag, text }) => (
          <button
            key={text}
            type="button"
            onClick={() => onPick(text)}
            className="group flex flex-col items-start gap-2 rounded-2xl bg-surface p-3.5 text-left shadow-apple transition-colors hover:bg-[var(--bg-hover)] active:scale-[0.99]"
          >
            <span className="inline-flex items-center gap-1.5 rounded-full bg-tone-secondaryTint px-2 py-0.5 text-[11px] font-semibold text-tone-secondary">
              <Icon className="h-3.5 w-3.5 shrink-0" aria-hidden />
              {tag}
            </span>
            <span className="text-[14px] leading-snug text-ink-primary">{text}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

export default function ChatWindow({
  messages,
  isPending,
  busy,
  onSend,
  onRetry,
  documents,
  selectedDocIds,
  onChangeSelectedDocs,
  onOpenDocuments,
}: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    bottomRef.current?.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: 'end' });
  }, [messages.length, isPending]);

  const isEmpty = messages.length === 0 && !isPending;
  const lastIndex = messages.length - 1;

  return (
    <div className="relative flex min-h-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto scrollbar-thin">
        {isEmpty ? (
          <EmptyState
            onPick={onSend}
            docCount={documents.length}
            onOpenDocuments={onOpenDocuments}
          />
        ) : (
          <div className="mx-auto max-w-3xl space-y-6 px-3 pb-44 pt-20 sm:px-5">
            {messages.map((m, i) => (
              <MessageBubble
                key={m.id}
                message={m}
                canRetry={i === lastIndex && !busy}
                onRetry={onRetry}
              />
            ))}
            {isPending && <TypingIndicator />}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      <ChatInput
        onSend={onSend}
        disabled={busy}
        documents={documents}
        selectedDocIds={selectedDocIds}
        onChangeSelected={onChangeSelectedDocs}
      />
    </div>
  );
}
