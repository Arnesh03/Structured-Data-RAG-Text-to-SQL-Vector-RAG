"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AlertCircle, ChevronRight, FileText, Terminal } from "lucide-react";
import type { Message } from "@/lib/types";
import { ResultTable } from "./ResultTable";
import { SqlBlock } from "./SqlBlock";
import { StageTrail } from "./StageTrail";
import { Badge, ROUTE_META, RouteBadge, cx } from "./ui";

function Disclosure({
  label,
  icon,
  children,
  defaultOpen = false,
}: {
  label: string;
  icon: React.ReactNode;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="overflow-hidden rounded-2xl ring-1 ring-hairline">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-center gap-2 bg-surface-2 px-4 py-3 text-[13px] font-medium text-muted transition hover:text-text"
      >
        <ChevronRight
          size={14}
          className={cx(
            "transition-transform duration-400 [transition-timing-function:var(--ease)]",
            open && "rotate-90",
          )}
        />
        {icon}
        {label}
      </button>
      {open && <div className="animate-fade-up space-y-3 p-3">{children}</div>}
    </div>
  );
}

export function MessageCard({ message }: { message: Message }) {
  if (message.role === "user") {
    return (
      <div className="animate-fade-up flex justify-end">
        <div className="max-w-[78%] rounded-[22px] rounded-br-md bg-accent px-5 py-3 text-[17px] leading-snug text-on-accent">
          {message.text}
        </div>
      </div>
    );
  }

  const meta = message.route ? ROUTE_META[message.route] : null;

  return (
    <div className="animate-fade-up flex flex-col gap-4 rounded-[22px] rounded-bl-md bg-surface p-5 shadow-[var(--shadow-sm)] ring-1 ring-hairline sm:p-6">
      {/* Header: which pipeline handled this, and how long it took. */}
      <div className="flex flex-wrap items-center gap-2.5">
        {message.route ? (
          <RouteBadge route={message.route} elapsed={message.elapsed} />
        ) : (
          <Badge tone="neutral">
            <span className="animate-dot size-1.5 rounded-full bg-current" />
            Routing
          </Badge>
        )}
        {meta && <span className="t-caption">{meta.blurb}</span>}
      </div>

      {message.error ? (
        <div className="flex items-start gap-2.5 rounded-2xl bg-surface-2 p-4 text-[15px] text-danger">
          <AlertCircle size={16} className="mt-0.5 shrink-0" />
          <div className="whitespace-pre-wrap">{message.error}</div>
        </div>
      ) : (
        <>
          {!message.done && message.stage && (
            <StageTrail stage={message.stage} route={message.route} />
          )}

          {message.text && (
            <div className="prose-answer">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.text}</ReactMarkdown>
            </div>
          )}

          {/*
            Evidence: the SQL that ran, or the passages that were retrieved.
            Both start collapsed - the answer is what the reader came for, and
            the working is there for whoever wants to check it.
          */}
          {message.sql && (
            <Disclosure
              label={`Generated SQL${
                message.rowCount !== undefined ? ` · ${message.rowCount} rows` : ""
              }`}
              icon={<Terminal size={13} />}
            >
              <SqlBlock sql={message.sql} />
              {message.columns && message.rows && (
                <ResultTable columns={message.columns} rows={message.rows} />
              )}
            </Disclosure>
          )}

          {message.sources && message.sources.length > 0 && (
            <>
              <div className="flex flex-wrap gap-2">
                {message.sources.map((s) => (
                  <Badge key={s.file} tone="rag">
                    <FileText size={11} />
                    {s.title}
                  </Badge>
                ))}
              </div>
              {message.chunks && message.chunks.length > 0 && (
                <Disclosure
                  label={`Retrieved passages · ${message.chunks.length}`}
                  icon={<FileText size={13} />}
                >
                  {message.chunks.map((c, i) => (
                    <div key={i} className="rounded-2xl bg-surface-2 p-4">
                      <div className="mb-2 flex items-center gap-2 text-[12px]">
                        <span className="font-medium text-rag">{c.title}</span>
                        {c.page !== null && (
                          <span className="text-faint">page {c.page + 1}</span>
                        )}
                      </div>
                      <p className="text-[14px] leading-relaxed text-muted">{c.text}</p>
                    </div>
                  ))}
                </Disclosure>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}
