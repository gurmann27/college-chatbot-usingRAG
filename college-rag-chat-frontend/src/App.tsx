import { useEffect, useState } from 'react';
import { BookMarked, Menu, PanelLeft, SquarePen } from 'lucide-react';
import Sidebar from './components/Sidebar';
import ChatWindow from './components/ChatWindow';
import DocumentPanel from './components/DocumentPanel';
import { useChatStore } from './hooks/useChatStore';
import { useDocuments } from './hooks/useDocuments';
import { cn } from './lib/utils';

export default function App() {
  const chat = useChatStore();
  const docs = useDocuments();

  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [desktopSidebarOpen, setDesktopSidebarOpen] = useState(true);
  const [docsOpen, setDocsOpen] = useState(false);
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);

  // Drop filter ids for documents that no longer exist
  useEffect(() => {
    if (docs.documents.length === 0) return;
    setSelectedDocIds((prev) => prev.filter((id) => docs.documents.some((d) => d.id === id)));
  }, [docs.documents]);

  // Standard desktop keyboard shortcut: Cmd/Ctrl + \ toggles the sidebar
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === '\\') {
        e.preventDefault();
        setDesktopSidebarOpen((v) => !v);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  const messages = chat.activeSession?.messages ?? [];
  const indexedCount = docs.documents.filter((d) => d.status === 'indexed').length;

  return (
    <div className="canvas-duotone flex h-full overflow-hidden text-ink-primary">
      <Sidebar
        sessions={chat.sessions}
        activeId={chat.activeId}
        onNewChat={chat.newChat}
        onSelect={chat.selectChat}
        onDelete={chat.deleteChat}
        mobileOpen={mobileSidebarOpen}
        desktopOpen={desktopSidebarOpen}
        onCloseMobile={() => setMobileSidebarOpen(false)}
        onCollapseDesktop={() => setDesktopSidebarOpen(false)}
      />

      <main className="relative flex min-w-0 flex-1 flex-col">
        {/* Floating Functional Toolbar (Liquid Glass + scroll edge fade) */}
        <header className="pointer-events-none absolute inset-x-0 top-0 z-20 px-3 pt-2.5 sm:px-4">
          <div className="scroll-edge-top pointer-events-none absolute inset-x-0 top-0 -z-10 h-20" aria-hidden />

          <div className="liquid-glass pointer-events-auto mx-auto flex h-12 max-w-4xl items-center gap-2 rounded-2xl px-2 sm:px-3">
            {/* Mobile drawer button */}
            <button
              type="button"
              onClick={() => setMobileSidebarOpen(true)}
              aria-label="Show sidebar"
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-ink-secondary transition-colors hover:bg-[var(--bg-hover)] hover:text-ink-primary md:hidden"
            >
              <Menu className="h-5 w-5" />
            </button>

            {/* Desktop sidebar toggle when hidden (or collapse/expand control) */}
            <button
              type="button"
              onClick={() => setDesktopSidebarOpen((v) => !v)}
              aria-label={desktopSidebarOpen ? 'Hide sidebar' : 'Show sidebar'}
              title={desktopSidebarOpen ? 'Hide sidebar (⌘\\)' : 'Show sidebar (⌘\\)'}
              className={cn(
                'hidden h-8 w-8 shrink-0 items-center justify-center rounded-lg text-ink-secondary transition-colors hover:bg-[var(--bg-hover)] hover:text-ink-primary md:flex',
              )}
            >
              <PanelLeft className="h-[18px] w-[18px]" />
            </button>

            <div className="flex min-w-0 flex-1 items-center gap-2 px-1">
              <h1 className="min-w-0 truncate text-[15px] font-semibold tracking-[-0.015em] text-ink-primary">
                {chat.activeSession?.title ?? 'New Chat'}
              </h1>
              {selectedDocIds.length > 0 && (
                <span className="hidden shrink-0 rounded-full bg-tone-secondaryTint px-2 py-0.5 text-[12px] font-medium tabular-nums text-tone-secondary sm:inline-flex">
                  {selectedDocIds.length} filtered
                </span>
              )}
            </div>

            <div className="flex shrink-0 items-center gap-1">
              {!desktopSidebarOpen && (
                <button
                  type="button"
                  onClick={chat.newChat}
                  aria-label="New Chat"
                  title="New Chat"
                  className="hidden h-8 items-center gap-1.5 rounded-lg px-2.5 text-[13px] font-medium text-ink-secondary transition-colors hover:bg-[var(--bg-hover)] hover:text-ink-primary md:inline-flex"
                >
                  <SquarePen className="h-4 w-4" />
                  <span>New Chat</span>
                </button>
              )}

              <button
                type="button"
                onClick={() => setDocsOpen(true)}
                aria-label="Knowledge Base"
                className="inline-flex h-10 items-center gap-1.5 rounded-xl px-2.5 text-[13px] font-medium text-ink-primary transition-colors hover:bg-[var(--bg-hover)] md:h-8 md:rounded-lg"
              >
                <BookMarked className="h-4 w-4 text-tone-secondary" aria-hidden />
                <span className="hidden sm:inline">Knowledge Base…</span>
                {indexedCount > 0 && (
                  <span className="rounded-full bg-tone-secondaryTint px-1.5 py-0.5 text-[11px] font-semibold tabular-nums text-tone-secondary">
                    {indexedCount}
                  </span>
                )}
              </button>
            </div>
          </div>
        </header>

        <ChatWindow
          messages={messages}
          isPending={chat.isPending}
          busy={chat.busy}
          onSend={(text) => chat.send(text, selectedDocIds)}
          onRetry={() => chat.retry(selectedDocIds)}
          documents={docs.documents}
          selectedDocIds={selectedDocIds}
          onChangeSelectedDocs={setSelectedDocIds}
          onOpenDocuments={() => setDocsOpen(true)}
        />
      </main>

      <DocumentPanel
        open={docsOpen}
        onClose={() => setDocsOpen(false)}
        documents={docs.documents}
        loading={docs.loading}
        error={docs.error}
        onRefresh={docs.refresh}
      />
    </div>
  );
}
