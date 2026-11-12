import { useEffect, useMemo, useState } from 'react';
import { Check, GraduationCap, MessageSquare, PanelLeftClose, SquarePen, Trash2, X } from 'lucide-react';
import type { ChatSession } from '../types';
import { cn, dayBucket } from '../lib/utils';

interface Props {
  sessions: ChatSession[];
  activeId: string | null;
  onNewChat: () => void;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  mobileOpen: boolean;
  desktopOpen: boolean;
  onCloseMobile: () => void;
  onCollapseDesktop: () => void;
}

const GROUP_ORDER = ['Today', 'Yesterday', 'Previous 7 days', 'Older'] as const;

export default function Sidebar({
  sessions,
  activeId,
  onNewChat,
  onSelect,
  onDelete,
  mobileOpen,
  desktopOpen,
  onCloseMobile,
  onCollapseDesktop,
}: Props) {
  // Two-step delete: first click shows confirm/cancel, second click confirms.
  const [confirmId, setConfirmId] = useState<string | null>(null);

  useEffect(() => {
    if (!confirmId) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setConfirmId(null);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [confirmId]);

  const groups = useMemo(() => {
    const map = new Map<string, ChatSession[]>();
    for (const s of [...sessions].sort((a, b) => b.updatedAt - a.updatedAt)) {
      const key = dayBucket(s.updatedAt);
      map.set(key, [...(map.get(key) ?? []), s]);
    }
    return GROUP_ORDER.filter((k) => map.has(k)).map((k) => ({ label: k, items: map.get(k)! }));
  }, [sessions]);

  const select = (id: string) => {
    onSelect(id);
    onCloseMobile();
  };

  return (
    <>
      {mobileOpen && (
        <div
          className="fixed inset-0 z-30 bg-[var(--scrim)] md:hidden"
          onClick={onCloseMobile}
          aria-hidden
        />
      )}

      <aside
        className={cn(
          'liquid-glass-sidebar fixed inset-y-0 left-0 z-40 flex w-[min(85vw,280px)] shrink-0 flex-col transition-all duration-200 ease-out',
          mobileOpen ? 'translate-x-0' : '-translate-x-full',
          'md:static md:translate-x-0',
          desktopOpen
            ? 'md:w-[272px] md:opacity-100'
            : 'md:w-0 md:overflow-hidden md:border-r-0 md:opacity-0 md:pointer-events-none',
        )}
        aria-label="Conversations"
        aria-hidden={!mobileOpen && !desktopOpen ? true : undefined}
      >
        {/* Brand header */}
        <div className="flex items-center justify-between px-4 pb-3 pt-3.5">
          <div className="flex min-w-0 items-center gap-2.5">
            <div
              className="brand-duotone flex h-8 w-8 shrink-0 items-center justify-center rounded-xl text-white shadow-sm"
              aria-hidden
            >
              <GraduationCap className="h-[18px] w-[18px]" />
            </div>
            <div className="min-w-0">
              <p className="truncate text-[15px] font-semibold tracking-[-0.015em] text-ink-primary">
                College Assistant
              </p>
              <p className="truncate text-[11px] font-medium text-ink-tertiary">
                Campus Knowledge Base
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onCloseMobile}
            aria-label="Close sidebar"
            className="flex h-11 w-11 items-center justify-center rounded-xl text-ink-secondary hover:bg-[var(--bg-hover)] hover:text-ink-primary md:hidden"
          >
            <X className="h-5 w-5" />
          </button>

          <button
            type="button"
            onClick={onCollapseDesktop}
            aria-label="Hide sidebar"
            title="Hide sidebar (⌘\)"
            className="hidden h-8 w-8 items-center justify-center rounded-lg text-ink-secondary transition-colors hover:bg-[var(--bg-hover)] hover:text-ink-primary md:flex"
          >
            <PanelLeftClose className="h-4 w-4" />
          </button>
        </div>

        {/* Primary sidebar action */}
        <div className="px-3 pb-2">
          <button
            type="button"
            onClick={() => {
              onNewChat();
              onCloseMobile();
            }}
            className="flex min-h-[40px] w-full items-center justify-center gap-2 rounded-xl bg-surface px-3 py-2 text-[14px] font-medium text-ink-primary shadow-apple transition-colors hover:bg-[var(--bg-hover)] active:scale-[0.99] md:min-h-[36px] md:text-[13px]"
          >
            <SquarePen className="h-4 w-4 text-accent-text" aria-hidden />
            New Chat
          </button>
        </div>

        {/* Grouped conversation list (max 2 hierarchy levels) */}
        <nav className="mt-2 min-h-0 flex-1 overflow-y-auto px-2.5 pb-4 scrollbar-thin">
          {groups.length === 0 && (
            <div className="px-3 py-10 text-center">
              <p className="text-[13px] font-medium text-ink-secondary">No conversations yet</p>
              <p className="mt-1 text-[12px] text-ink-tertiary">
                Ask a question to start your first thread.
              </p>
            </div>
          )}

          {groups.map(({ label, items }) => (
            <div key={label} className="mb-4">
              <h2 className="px-2.5 pb-1.5 text-[11px] font-semibold tracking-[0.02em] text-ink-tertiary">
                {label}
              </h2>
              <ul className="space-y-0.5">
                {items.map((s) => {
                  const active = s.id === activeId;
                  const confirming = confirmId === s.id;
                  return (
                    <li key={s.id} className="group relative">
                      <button
                        type="button"
                        onClick={() => select(s.id)}
                        aria-current={active ? 'page' : undefined}
                        className={cn(
                          'flex min-h-[40px] w-full items-center gap-2.5 rounded-xl px-2.5 py-2 pr-16 text-left text-[14px] transition-colors md:min-h-[34px] md:rounded-lg md:py-1.5 md:text-[13px]',
                          active
                            ? 'bg-[var(--sidebar-active-bg)] font-semibold text-accent-text shadow-apple'
                            : 'text-ink-primary hover:bg-[var(--bg-hover)]',
                        )}
                      >
                        <MessageSquare
                          className={cn(
                            'h-4 w-4 shrink-0',
                            active ? 'text-accent-text' : 'text-ink-tertiary',
                          )}
                          aria-hidden
                        />
                        <span className="truncate">{s.title}</span>
                      </button>

                      <div
                        className={cn(
                          'absolute right-1.5 top-1/2 flex -translate-y-1/2 items-center gap-0.5 transition-opacity',
                          !confirming &&
                            'md:opacity-0 md:group-focus-within:opacity-100 md:group-hover:opacity-100',
                        )}
                      >
                        {confirming ? (
                          <>
                            <button
                              type="button"
                              onClick={() => {
                                onDelete(s.id);
                                setConfirmId(null);
                              }}
                              aria-label={`Confirm delete ${s.title}`}
                              title="Confirm delete"
                              className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--signal-red-bg)] text-[var(--signal-red-text)] transition-colors md:h-7 md:w-7"
                            >
                              <Check className="h-3.5 w-3.5" />
                            </button>
                            <button
                              type="button"
                              onClick={() => setConfirmId(null)}
                              aria-label="Cancel delete"
                              title="Cancel (Esc)"
                              className="flex h-8 w-8 items-center justify-center rounded-lg bg-secondary text-ink-secondary transition-colors hover:text-ink-primary md:h-7 md:w-7"
                            >
                              <X className="h-3.5 w-3.5" />
                            </button>
                          </>
                        ) : (
                          <button
                            type="button"
                            onClick={() => setConfirmId(s.id)}
                            aria-label={`Delete ${s.title}`}
                            title="Delete conversation"
                            className="flex h-8 w-8 items-center justify-center rounded-lg text-ink-tertiary transition-colors hover:bg-[var(--signal-red-bg)] hover:text-[var(--signal-red-text)] md:h-7 md:w-7"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        )}
                      </div>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>
      </aside>
    </>
  );
}
