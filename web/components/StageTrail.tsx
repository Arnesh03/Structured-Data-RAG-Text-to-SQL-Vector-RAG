"use client";

import { Check } from "lucide-react";
import type { Route, Stage } from "@/lib/types";
import { cx } from "./ui";

const LABELS: Record<Stage, string> = {
  routing: "Reading the question",
  generating_sql: "Writing SQL",
  executing_sql: "Running the query",
  retrieving: "Searching the documents",
  answering: "Composing the answer",
};

const PIPELINES: Record<Route, Stage[]> = {
  sql: ["routing", "generating_sql", "executing_sql", "answering"],
  rag: ["routing", "retrieving", "answering"],
};

/**
 * The pipeline as it runs: past stages tick off, the current one pulses.
 *
 * Before the router has answered we only know the first stage, so the trail
 * grows once the route is known rather than guessing which branch it will take.
 */
export function StageTrail({ stage, route }: { stage: Stage; route?: Route }) {
  const stages = route ? PIPELINES[route] : (["routing"] as Stage[]);
  const current = stages.indexOf(stage);

  return (
    <ol className="flex flex-col gap-2 text-[14px]">
      {stages.map((s, i) => {
        const done = current > i;
        const active = current === i;
        return (
          <li
            key={s}
            className={cx(
              "flex items-center gap-2.5 transition-colors duration-500",
              done && "text-faint",
              active && "text-text",
              !done && !active && "text-faint opacity-40",
            )}
          >
            <span className="flex size-4 shrink-0 items-center justify-center">
              {done ? (
                <Check size={13} strokeWidth={3} className="text-accent" />
              ) : (
                <span
                  className={cx(
                    "size-1.5 rounded-full",
                    active ? "animate-dot bg-accent" : "bg-current",
                  )}
                />
              )}
            </span>
            {LABELS[s]}
          </li>
        );
      })}
    </ol>
  );
}
