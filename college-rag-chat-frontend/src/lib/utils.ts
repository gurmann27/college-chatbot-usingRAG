/** Join class names, skipping falsy values. */
export const cn = (...classes: Array<string | false | null | undefined>) =>
  classes.filter(Boolean).join(' ');

/** Unique id (crypto.randomUUID with a fallback for older browsers / insecure contexts). */
export const uid = (): string =>
  typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;

export function formatBytes(bytes?: number): string {
  if (bytes === undefined || bytes === null) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatDate(ts: number): string {
  return new Date(ts).toLocaleDateString(undefined, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
}

/** Group label used by the sidebar history list. */
export function dayBucket(ts: number): 'Today' | 'Yesterday' | 'Previous 7 days' | 'Older' {
  const startOfToday = new Date();
  startOfToday.setHours(0, 0, 0, 0);
  const dayMs = 24 * 60 * 60 * 1000;
  const diff = startOfToday.getTime() - ts;
  if (diff <= 0) return 'Today';
  if (diff <= dayMs) return 'Yesterday';
  if (diff <= 7 * dayMs) return 'Previous 7 days';
  return 'Older';
}

/** "0.83" -> "83%"; values above 1 (e.g. raw reranker logits) -> "4.21". */
export function formatScore(score: number): string {
  if (score >= 0 && score <= 1) return `${Math.round(score * 100)}%`;
  return score.toFixed(2);
}

/** Semantic pill styling for relevance scores (light & dark via CSS variables). */
export function scoreTone(score: number): string {
  if (score >= 0.75) {
    return 'bg-[var(--signal-green-bg)] text-[var(--signal-green-text)] ring-[var(--signal-green-ring)]';
  }
  if (score >= 0.5) {
    return 'bg-[var(--signal-amber-bg)] text-[var(--signal-amber-text)] ring-[var(--signal-amber-ring)]';
  }
  return 'bg-secondary text-ink-secondary ring-separator';
}

const LANGUAGE_LABELS: Record<string, string> = {
  en: 'English',
  hi: 'हिन्दी',
  'hi-latn': 'Hinglish',
  ta: 'தமிழ்',
  te: 'తెలుగు',
  mr: 'मराठी',
  bn: 'বাংলা',
  kn: 'ಕನ್ನಡ',
};

export function formatLanguage(code?: string | null): string | null {
  if (!code) return null;
  const key = code.trim().toLowerCase();
  return LANGUAGE_LABELS[key] ?? code.toUpperCase();
}

export function formatCategory(category?: string | null): string | null {
  if (!category) return null;
  return category.charAt(0).toUpperCase() + category.slice(1).toLowerCase();
}

export function makeTitle(text: string, max = 44): string {
  const clean = text.replace(/\s+/g, ' ').trim();
  return clean.length > max ? `${clean.slice(0, max - 1)}…` : clean;
}
