import { useState } from 'react';
import ReactMarkdown, { type Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { Check, Copy } from 'lucide-react';

interface Props {
  content: string;
  /** Called with the 1-based source number when a [n] badge is clicked. */
  onCitationClick?: (n: number) => void;
}

/**
 * Turns bare "[1]" markers into markdown links ("#cite-1") so we can render
 * them as clickable badges. Fenced and inline code are left untouched so
 * things like `arr[0]` aren't affected.
 */
function linkifyCitations(text: string): string {
  return text
    .split(/(```[\s\S]*?```|`[^`\n]*`)/g)
    .map((part, i) =>
      i % 2 === 1 ? part : part.replace(/\[(\d{1,2})\](?!\()/g, '[$1](#cite-$1)'),
    )
    .join('');
}

function CodeBlock({ language, code }: { language: string; code: string }) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable */
    }
  };

  return (
    <div className="not-prose my-3 overflow-hidden rounded-xl border border-separator bg-[#1e2024]">
      <div className="flex items-center justify-between border-b border-white/10 bg-[#26292e] px-3 py-1.5 text-xs text-[#d4d4d8]">
        <span className="font-mono">{language || 'text'}</span>
        <button
          type="button"
          onClick={copy}
          className="inline-flex min-h-[28px] items-center gap-1 rounded-md px-2 py-1 hover:bg-white/10"
        >
          {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <SyntaxHighlighter
        language={language || 'text'}
        style={oneDark}
        PreTag="div"
        customStyle={{ margin: 0, padding: '0.75rem 1rem', background: 'transparent', fontSize: '0.8125rem' }}
      >
        {code}
      </SyntaxHighlighter>
    </div>
  );
}

export default function MarkdownRenderer({ content, onCitationClick }: Props) {
  const components: Components = {
    a: ({ href, children }) => {
      if (href?.startsWith('#cite-')) {
        const n = Number(href.slice(6));
        return (
          <button
            type="button"
            onClick={() => onCitationClick?.(n)}
            title={`Jump to source ${n}`}
            aria-label={`Source ${n}`}
            className="mx-0.5 inline-flex h-[20px] min-w-[20px] -translate-y-px items-center justify-center rounded-full bg-accent-tint px-1.5 align-baseline text-[11px] font-semibold tabular-nums text-accent-text transition-colors hover:bg-accent hover:text-white"
          >
            {n}
          </button>
        );
      }
      return (
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="font-medium text-accent-text underline-offset-2 hover:underline"
        >
          {children}
        </a>
      );
    },
    pre: ({ children }) => <>{children}</>,
    code: ({ node, className, children, ...rest }) => {
      const text = String(children ?? '');
      const language = /language-([\w-]+)/.exec(className ?? '')?.[1];
      const isBlock = Boolean(language) || text.includes('\n');
      if (isBlock) {
        return <CodeBlock language={language ?? ''} code={text.replace(/\n$/, '')} />;
      }
      return (
        <code
          {...rest}
          className="rounded-md bg-secondary px-1.5 py-0.5 font-mono text-[0.85em] font-normal text-ink-primary before:content-none after:content-none"
        >
          {children}
        </code>
      );
    },
    table: ({ children }) => (
      <div className="not-prose my-3 overflow-x-auto rounded-xl border border-separator">
        <table className="min-w-full divide-y divide-separator text-[13px]">{children}</table>
      </div>
    ),
    th: ({ children }) => (
      <th className="bg-secondary/60 px-3 py-2 text-left font-semibold text-ink-primary">{children}</th>
    ),
    td: ({ children }) => (
      <td className="border-t border-separator px-3 py-2 text-ink-primary">{children}</td>
    ),
  };

  return (
    <div className="prose prose-sm max-w-none break-words text-[15px] leading-[1.55] text-ink-primary dark:prose-invert prose-headings:text-ink-primary prose-p:leading-relaxed prose-p:text-ink-primary prose-strong:text-ink-primary prose-li:my-0.5 prose-li:text-ink-primary prose-a:text-accent-text">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {linkifyCitations(content)}
      </ReactMarkdown>
    </div>
  );
}
