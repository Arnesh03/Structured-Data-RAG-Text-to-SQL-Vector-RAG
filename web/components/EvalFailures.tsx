"use client";

import { useState } from "react";
import { ChevronRight } from "lucide-react";
import { Card, CardHeader, cx } from "@/components/ui";
import type { EvalFailure, FailureKind } from "@/lib/types";

/**
 * Failures are ordered by how much they should worry you, not by question id.
 *
 * A hallucination on an unanswerable question is the worst thing this system
 * can do, so it sorts first and carries the red. A misroute is recoverable and
 * reads amber.
 */
const KIND_TONE: Record<FailureKind, "bad" | "warn"> = {
  hallucinated: "bad",
  errored: "bad",
  misrouted: "warn",
  "wrong answer": "warn",
};

const KIND_BLURB: Record<FailureKind, string> = {
  hallucinated: "Answered a question with no answer in the corpus",
  misrouted: "Sent to the wrong arm",
  "wrong answer": "Right arm, wrong answer",
  errored: "The pipeline raised",
};

const TONE_CHIP = {
  bad: "bg-danger-soft text-danger",
  warn: "bg-warn-soft text-warn",
} as const;

function FailureRow({ failure }: { failure: EvalFailure }) {
  const [open, setOpen] = useState(false);
  const tone = KIND_TONE[failure.kind] ?? "warn";

  return (
    <div className="border-b border-hairline last:border-0">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-start gap-3 py-3.5 text-left"
      >
        <ChevronRight
          size={15}
          className={cx(
            "mt-1 shrink-0 text-faint transition-transform duration-300",
            open && "rotate-90",
          )}
        />
        <span className="min-w-0 flex-1">
          <span className="block text-[15px] leading-snug">{failure.question}</span>
          <span className="mt-1.5 flex flex-wrap items-center gap-1.5">
            <span
              className={cx(
                "rounded-full px-2 py-0.5 text-[11px] font-medium",
                TONE_CHIP[tone],
              )}
            >
              {failure.kind}
            </span>
            <span className="t-caption font-mono">{failure.question_id}</span>
            <span className="t-caption">· {failure.category}</span>
            {failure.fallback_used && (
              <span className="t-caption text-warn">· keyword fallback fired</span>
            )}
          </span>
        </span>
      </button>

      {open && (
        <div className="animate-fade-up space-y-3 pb-4 pl-8 text-[14px]">
          <p className="t-caption">{KIND_BLURB[failure.kind]}</p>

          <div className="flex flex-wrap gap-x-6 gap-y-1 text-[13px]">
            <span>
              <span className="text-faint">expected route </span>
              <span className="font-mono">{failure.expected_route ?? "none — unanswerable"}</span>
            </span>
            <span>
              <span className="text-faint">got </span>
              <span className="font-mono">{failure.actual_route ?? "none"}</span>
            </span>
          </div>

          <div>
            <p className="t-caption mb-1">What it answered</p>
            <p className="rounded-[10px] bg-surface-2 p-3 leading-relaxed">
              {failure.answer || "(no answer)"}
            </p>
          </div>

          {failure.sql_query && (
            <div className="grid gap-3 lg:grid-cols-2">
              <div>
                <p className="t-caption mb-1">Generated SQL</p>
                <pre className="overflow-x-auto rounded-[10px] bg-surface-2 p-3 font-mono text-[12.5px] leading-relaxed">
                  {failure.sql_query}
                </pre>
              </div>
              {failure.gold_sql && (
                <div>
                  <p className="t-caption mb-1">Gold SQL</p>
                  <pre className="overflow-x-auto rounded-[10px] bg-positive-soft p-3 font-mono text-[12.5px] leading-relaxed">
                    {failure.gold_sql}
                  </pre>
                </div>
              )}
            </div>
          )}

          {(failure.sources.length > 0 || failure.gold_doc_ids) && (
            <div className="flex flex-wrap gap-x-6 gap-y-1 text-[13px]">
              <span>
                <span className="text-faint">retrieved </span>
                <span className="font-mono">{failure.sources.join(", ") || "nothing"}</span>
              </span>
              {failure.gold_doc_ids && (
                <span>
                  <span className="text-faint">expected </span>
                  <span className="font-mono">{failure.gold_doc_ids.join(", ")}</span>
                </span>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function Failures({ failures }: { failures: EvalFailure[] }) {
  const [kind, setKind] = useState<FailureKind | "all">("all");

  const kinds = Array.from(new Set(failures.map((f) => f.kind)));
  const shown = kind === "all" ? failures : failures.filter((f) => f.kind === kind);

  if (failures.length === 0) {
    return (
      <Card>
        <CardHeader
          title="Failures"
          hint="Nothing failed in this run. Check that the golden set is actually hard enough — a set with no failures has stopped measuring."
        />
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader
        title={`Failures (${failures.length})`}
        hint="Ordered by severity. This is the panel that tells you what to fix next."
      />

      <div className="mb-1 flex flex-wrap gap-2">
        {(["all", ...kinds] as const).map((option) => (
          <button
            key={option}
            type="button"
            onClick={() => setKind(option as FailureKind | "all")}
            className={cx(
              "rounded-full px-3 py-1.5 text-[12.5px] font-medium transition-colors duration-200",
              kind === option
                ? "bg-text text-bg"
                : "bg-surface-2 text-muted hover:text-text",
            )}
          >
            {option}
            {option !== "all" && (
              <span className="ml-1.5 opacity-60 tabular-nums">
                {failures.filter((f) => f.kind === option).length}
              </span>
            )}
          </button>
        ))}
      </div>

      <div>
        {shown.map((failure) => (
          <FailureRow key={failure.question_id} failure={failure} />
        ))}
      </div>
    </Card>
  );
}
