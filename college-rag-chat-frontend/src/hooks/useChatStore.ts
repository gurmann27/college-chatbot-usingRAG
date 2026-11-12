import { useCallback, useEffect, useState } from 'react';
import { ApiError, deleteSession, getHistory, sendChat } from '../services/api';
import type { ChatSession, Message } from '../types';
import { makeTitle, uid } from '../lib/utils';

const STORAGE_KEY = 'college-rag:sessions:v1';

function loadSessions(): ChatSession[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as ChatSession[]) : [];
  } catch {
    return [];
  }
}

/**
 * Owns all chat state: sessions, the active session and the in-flight request.
 *
 *  - Sessions are cached in localStorage so history survives a refresh.
 *  - On mount, GET /api/v1/history is merged in (server-only sessions are added).
 *  - A new session is created lazily on the first message, using a client-generated
 *    UUID as `session_id`. The backend should treat it as an opaque id.
 */
export function useChatStore() {
  const [sessions, setSessions] = useState<ChatSession[]>(loadSessions);
  const [activeId, setActiveId] = useState<string | null>(null); // null = "New chat"
  const [pendingId, setPendingId] = useState<string | null>(null); // session awaiting a reply

  // Persist to localStorage
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
    } catch {
      /* storage full or blocked – ignore */
    }
  }, [sessions]);

  // Merge server history once on mount
  useEffect(() => {
    let cancelled = false;
    getHistory()
      .then((remote) => {
        if (cancelled || remote.length === 0) return;
        setSessions((local) => {
          const known = new Set(local.map((s) => s.id));
          const added = remote.filter((s) => !known.has(s.id));
          return added.length ? [...local, ...added].sort((a, b) => b.updatedAt - a.updatedAt) : local;
        });
      })
      .catch(() => {
        /* History is a nice-to-have; local cache still works */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const activeSession = sessions.find((s) => s.id === activeId) ?? null;

  const appendMessage = useCallback((sessionId: string, message: Message) => {
    setSessions((prev) =>
      prev.map((s) =>
        s.id === sessionId
          ? { ...s, messages: [...s.messages, message], updatedAt: Date.now() }
          : s,
      ),
    );
  }, []);

  /** Calls the backend and appends either the answer or an error bubble. */
  const ask = useCallback(
    async (sessionId: string, query: string, documentIds: string[]) => {
      setPendingId(sessionId);
      try {
        const res = await sendChat({
          query,
          session_id: sessionId,
          document_ids: documentIds.length ? documentIds : undefined,
        });
        appendMessage(sessionId, {
          id: res.message_id ?? uid(),
          role: 'assistant',
          content: res.answer,
          sources: res.sources,
          createdAt: Date.now(),
          abstained: res.abstained,
          language: res.language,
        });
      } catch (e) {
        const reason = e instanceof ApiError ? e.message : 'Something went wrong.';
        appendMessage(sessionId, {
          id: uid(),
          role: 'assistant',
          content: `Sorry, I couldn't get an answer. ${reason}`,
          createdAt: Date.now(),
          error: true,
        });
      } finally {
        setPendingId(null);
      }
    },
    [appendMessage],
  );

  const send = useCallback(
    async (text: string, documentIds: string[]) => {
      const query = text.trim();
      if (!query || pendingId !== null) return;

      const sessionId = activeId ?? uid();
      const now = Date.now();
      const userMessage: Message = { id: uid(), role: 'user', content: query, createdAt: now };

      setSessions((prev) =>
        prev.some((s) => s.id === sessionId)
          ? prev.map((s) =>
              s.id === sessionId
                ? { ...s, messages: [...s.messages, userMessage], updatedAt: now }
                : s,
            )
          : [
              {
                id: sessionId,
                title: makeTitle(query),
                createdAt: now,
                updatedAt: now,
                messages: [userMessage],
              },
              ...prev,
            ],
      );
      setActiveId(sessionId);
      await ask(sessionId, query, documentIds);
    },
    [activeId, pendingId, ask],
  );

  /** Re-sends the last user question after a failed request. */
  const retry = useCallback(
    async (documentIds: string[]) => {
      if (!activeSession || pendingId !== null) return;
      const { messages } = activeSession;
      if (!messages[messages.length - 1]?.error) return;
      const lastUser = [...messages].reverse().find((m) => m.role === 'user');
      if (!lastUser) return;

      // Drop the error bubble, then ask again
      setSessions((prev) =>
        prev.map((s) =>
          s.id === activeSession.id ? { ...s, messages: s.messages.slice(0, -1) } : s,
        ),
      );
      await ask(activeSession.id, lastUser.content, documentIds);
    },
    [activeSession, pendingId, ask],
  );

  const newChat = useCallback(() => setActiveId(null), []);
  const selectChat = useCallback((id: string) => setActiveId(id), []);

  const deleteChat = useCallback(
    (id: string) => {
      setSessions((prev) => prev.filter((s) => s.id !== id));
      setActiveId((cur) => (cur === id ? null : cur));
      deleteSession(id).catch(() => {
        /* best effort – the local copy is already gone */
      });
    },
    [],
  );

  return {
    sessions,
    activeId,
    activeSession,
    /** True while waiting for a reply in the *currently visible* chat. */
    isPending: pendingId !== null && pendingId === activeId,
    /** True while any request is in flight (used to block sending). */
    busy: pendingId !== null,
    send,
    retry,
    newChat,
    selectChat,
    deleteChat,
  };
}
