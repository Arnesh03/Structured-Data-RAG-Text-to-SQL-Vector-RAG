"use client";

import { CountUp, Card, CardHeader, cx } from "@/components/ui";
import {
  LOWER_IS_BETTER,
  METRIC_GROUPS,
  METRIC_HINTS,
  TONE_BG,
  TONE_TEXT,
  TONE_VAR,
  label,
  toneOf,
} from "@/lib/metrics";
import type { Metrics } from "@/lib/types";

/* ── One metric ────────────────────────────────────────────────────── */

/**
 * A metric as a number, a bar and a colour.
 *
 * The bar always shows the raw value, while the colour comes from the
 * threshold: a 4% hallucination rate is a short bar AND a green one, which is
 * the right reading. Colouring the bar by length instead would make every
 * lower-is-better metric look like a failure.
 */
export function MetricTile({
  metric,
  value,
  delay = 0,
}: {
  metric: string;
  value: number;
  delay?: number;
}) {
  const tone = toneOf(metric, value);
  const hint = METRIC_HINTS[metric];
  const inverted = LOWER_IS_BETTER.has(metric);

  return (
    <div className="rounded-[14px] bg-surface-2 p-4">
      <div className="flex items-center gap-1.5">
        <span className="text-[13px] font-medium text-muted">{label(metric)}</span>
        {inverted && (
          <span className="t-caption text-[10px] tabular-nums" title="lower is better">
            ↓
          </span>
        )}
      </div>

      <div className={cx("t-numeral mt-1.5 text-[26px]", TONE_TEXT[tone])}>
        <CountUp
          value={value}
          duration={900}
          format={(n) => `${(n * 100).toFixed(1)}%`}
        />
      </div>

      <div className="mt-2.5 h-1.5 overflow-hidden rounded-full bg-surface-3">
        <div
          className="h-full rounded-full transition-[width] duration-1000 [transition-delay:var(--d)] [transition-timing-function:var(--ease)]"
          style={{
            width: `${Math.min(100, Math.max(0, value * 100))}%`,
            background: TONE_VAR[tone],
            "--d": `${delay}ms`,
          } as React.CSSProperties}
        />
      </div>

      {hint && <p className="t-caption mt-2.5 leading-snug">{hint}</p>}
    </div>
  );
}

/* ── Grouped metrics ───────────────────────────────────────────────── */

export function MetricGroups({ metrics }: { metrics: Metrics }) {
  const groups = METRIC_GROUPS.map((group) => ({
    ...group,
    present: group.metrics.filter((m) => metrics[m] !== undefined),
  })).filter((group) => group.present.length > 0);

  if (groups.length === 0) {
    return (
      <Card>
        <p className="text-[15px] text-muted">
          This run has traces but no scores yet. Score it with{" "}
          <code className="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-[13px]">
            make eval-score
          </code>
          .
        </p>
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-5">
      {groups.map((group) => (
        <Card key={group.id}>
          <CardHeader title={group.title} hint={group.blurb} />
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {group.present.map((metric, i) => (
              <MetricTile
                key={metric}
                metric={metric}
                value={metrics[metric]}
                delay={i * 70}
              />
            ))}
          </div>
        </Card>
      ))}
    </div>
  );
}

/* ── Confusion matrix ──────────────────────────────────────────────── */

const ROUTE_NAME: Record<string, string> = { sql: "Text-to-SQL", rag: "Vector RAG" };

/**
 * Where the router sent things, and where it should have.
 *
 * The direction of the error is the finding: "aggregates leak into the policy
 * arm" is actionable in a way that "93% accurate" is not. The diagonal reads
 * green, anything off it reads red once it is non-zero.
 */
export function ConfusionMatrix({
  confusion,
}: {
  confusion: Record<string, Record<string, number>>;
}) {
  const rows = Object.keys(confusion);
  const columns = ["sql", "rag", "None"];

  return (
    <Card>
      <CardHeader
        title="Router confusion"
        hint="Rows are the arm the question needed; columns are the arm it reached."
      />
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-[14px]">
          <thead>
            <tr>
              <th className="t-caption px-3 py-2 text-left font-medium">expected ╲ got</th>
              {columns.map((column) => (
                <th key={column} className="t-caption px-3 py-2 text-center font-medium">
                  {ROUTE_NAME[column] ?? "no route"}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row}>
                <td className="px-3 py-2 font-medium">{ROUTE_NAME[row] ?? row}</td>
                {columns.map((column) => {
                  const count = confusion[row]?.[column] ?? 0;
                  const diagonal = row === column;
                  const tone = count === 0 ? "neutral" : diagonal ? "good" : "bad";
                  return (
                    <td key={column} className="px-1.5 py-1.5">
                      <div
                        className={cx(
                          "rounded-[10px] py-2.5 text-center tabular-nums",
                          "t-numeral text-[17px]",
                          TONE_BG[tone],
                          TONE_TEXT[tone],
                          count === 0 && "opacity-45",
                        )}
                      >
                        {count}
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

/* ── Slices ────────────────────────────────────────────────────────── */

/**
 * Metrics broken down by question category.
 *
 * Aggregates hide everything useful: "precision@5 is 0.81 overall but 0.52 on
 * multi-hop questions" is a finding, while "precision@5 is 0.81" is a
 * statistic. This table is where the first one shows up.
 */
export function SliceTable({
  title,
  hint,
  slices,
}: {
  title: string;
  hint: string;
  slices: Record<string, Metrics>;
}) {
  const buckets = Object.keys(slices);
  if (buckets.length === 0) return null;

  // Only show metrics that at least one bucket actually scored.
  const columns = METRIC_GROUPS.flatMap((g) => g.metrics).filter((metric) =>
    buckets.some((bucket) => slices[bucket][metric] !== undefined),
  );
  if (columns.length === 0) return null;

  return (
    <Card>
      <CardHeader title={title} hint={hint} />
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-[14px]">
          <thead>
            <tr className="border-b border-hairline">
              <th className="t-caption px-3 py-2 text-left font-medium">bucket</th>
              {columns.map((metric) => (
                <th
                  key={metric}
                  className="t-caption whitespace-nowrap px-3 py-2 text-right font-medium"
                >
                  {label(metric)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {buckets.map((bucket) => (
              <tr key={bucket} className="border-b border-hairline last:border-0">
                <td className="whitespace-nowrap px-3 py-2.5 font-mono text-[13px]">
                  {bucket}
                </td>
                {columns.map((metric) => {
                  const value = slices[bucket][metric];
                  if (value === undefined) {
                    return (
                      <td key={metric} className="px-3 py-2.5 text-right text-faint">
                        —
                      </td>
                    );
                  }
                  const tone = toneOf(metric, value);
                  return (
                    <td key={metric} className="px-1.5 py-1.5 text-right">
                      <span
                        className={cx(
                          "inline-block min-w-[56px] rounded-[8px] px-2 py-1",
                          "tabular-nums",
                          TONE_BG[tone],
                          TONE_TEXT[tone],
                        )}
                      >
                        {(value * 100).toFixed(0)}%
                      </span>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
