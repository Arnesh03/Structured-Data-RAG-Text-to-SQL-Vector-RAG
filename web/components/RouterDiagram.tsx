"use client";

import { Database, FileText, MessageSquareText, Sparkles } from "lucide-react";

/**
 * The architecture, drawn and animated: a question enters, the router splits
 * it, one of two pipelines answers.
 *
 * The connectors are SVG paths with a marching dash pattern, so the diagram
 * reads as something in motion rather than a static picture. Nodes are HTML
 * positioned over the SVG so their labels stay real text.
 */
export function RouterDiagram() {
  return (
    <div className="relative mx-auto w-full max-w-3xl select-none">
      <svg
        viewBox="0 0 720 200"
        className="w-full"
        role="img"
        aria-label="A question flows into an LLM router, which sends it to either the Text-to-SQL pipeline or the Vector RAG pipeline."
      >
        <g fill="none" strokeWidth="1.75" strokeLinecap="round">
          {/* question -> router */}
          <path d="M116 100 H316" stroke="var(--hairline-strong)" />
          <path d="M116 100 H316" stroke="var(--accent)" className="animate-flow" />

          {/* router -> sql (up) */}
          <path
            d="M408 100 H436 Q452 100 452 84 V56 Q452 40 468 40 H506"
            stroke="var(--hairline-strong)"
          />
          <path
            d="M408 100 H436 Q452 100 452 84 V56 Q452 40 468 40 H506"
            stroke="var(--sql)"
            className="animate-flow"
            style={{ animationDelay: "0.25s" }}
          />

          {/* router -> rag (down) */}
          <path
            d="M408 100 H436 Q452 100 452 116 V144 Q452 160 468 160 H506"
            stroke="var(--hairline-strong)"
          />
          <path
            d="M408 100 H436 Q452 100 452 116 V144 Q452 160 468 160 H506"
            stroke="var(--rag)"
            className="animate-flow"
            style={{ animationDelay: "0.55s" }}
          />
        </g>
      </svg>

      <Node className="left-0 top-1/2 -translate-y-1/2" tone="neutral">
        <MessageSquareText size={15} strokeWidth={2} />
        Question
      </Node>

      <Node className="left-[50.3%] top-1/2 -translate-x-1/2 -translate-y-1/2" tone="accent">
        <Sparkles size={15} strokeWidth={2} />
        LLM router
      </Node>

      <Node className="left-[70.3%] top-[20%] -translate-y-1/2" tone="sql">
        <Database size={15} strokeWidth={2} />
        Text-to-SQL
      </Node>

      <Node className="left-[70.3%] top-[80%] -translate-y-1/2" tone="rag">
        <FileText size={15} strokeWidth={2} />
        Vector RAG
      </Node>
    </div>
  );
}

function Node({
  children,
  className,
  tone,
}: {
  children: React.ReactNode;
  className: string;
  tone: "neutral" | "accent" | "sql" | "rag";
}) {
  const tones = {
    neutral: "bg-surface-2 text-muted",
    accent: "bg-accent text-on-accent shadow-[var(--shadow-md)]",
    sql: "bg-sql-soft text-sql",
    rag: "bg-rag-soft text-rag",
  };
  return (
    <span
      className={`absolute flex items-center gap-2 whitespace-nowrap rounded-full px-3.5 py-2 text-[13px] font-medium ${tones[tone]} ${className}`}
    >
      {children}
    </span>
  );
}
