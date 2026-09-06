"use client";

import { Fragment, useState } from "react";
import { Check, Copy } from "lucide-react";

const KEYWORDS = new Set([
  "select", "from", "where", "group", "by", "order", "limit", "having", "with",
  "as", "and", "or", "not", "in", "on", "join", "left", "inner", "outer", "case",
  "when", "then", "else", "end", "distinct", "count", "sum", "avg", "min", "max",
  "round", "cast", "desc", "asc", "like", "between", "null", "is", "union", "all",
]);

/**
 * Minimal SQL highlighting.
 *
 * A tokenizer beats a syntax-highlighting dependency here: the grammar we
 * generate is small and known, and this keeps the bundle honest.
 */
function highlight(sql: string) {
  const parts = sql.split(/(\s+|[(),]|'[^']*')/g);
  return parts.map((part, i) => {
    if (!part) return null;
    const lower = part.toLowerCase();
    let cls = "";
    if (KEYWORDS.has(lower)) cls = "text-sql font-semibold";
    else if (/^'.*'$/.test(part)) cls = "text-positive";
    else if (/^\d+(\.\d+)?$/.test(part)) cls = "text-rag";
    else if (/^[(),]$/.test(part)) cls = "text-faint";
    return cls ? (
      <span key={i} className={cls}>{part}</span>
    ) : (
      <Fragment key={i}>{part}</Fragment>
    );
  });
}

export function SqlBlock({ sql }: { sql: string }) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(sql);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      /* clipboard blocked - the SQL is selectable anyway */
    }
  };

  return (
    <div className="relative rounded-2xl bg-surface-2">
      <button
        type="button"
        onClick={copy}
        aria-label="Copy SQL"
        className="absolute right-2.5 top-2.5 flex size-8 items-center justify-center rounded-full text-faint transition hover:bg-surface-3 hover:text-text"
      >
        {copied ? <Check size={14} className="text-accent" /> : <Copy size={14} />}
      </button>
      <pre className="overflow-x-auto p-4 pr-12 text-[13px] leading-relaxed">
        <code className="font-mono">{highlight(sql)}</code>
      </pre>
    </div>
  );
}
