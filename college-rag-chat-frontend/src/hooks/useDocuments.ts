import { useCallback, useEffect, useState } from 'react';
import { listDocuments } from '../services/api';
import type { IndexedDocument } from '../types';

/** Loads the list of indexed documents and exposes a manual refresh. */
export function useDocuments() {
  const [documents, setDocuments] = useState<IndexedDocument[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setDocuments(await listDocuments());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load documents.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { documents, loading, error, refresh };
}
