"use client";

import { useEffect, useState } from "react";
import { FlaskConical, GitCommitHorizontal, ShieldCheck } from "lucide-react";
import { ConfusionMatrix, MetricGroups, SliceTable } from "@/components/EvalMetrics";
import { Failures } from "@/components/EvalFailures";
import { Card, CardHeader, ErrorNote, Reveal, Skeleton, cx } from "@/components/ui";
import { getEvalDataset, getEvalRun, getEvalSummary } from "@/lib/api";
import { METRIC_GROUPS, TONE_BG, TONE_TEXT, label, toneOf } from "@/lib/metrics";
import type { EvalDataset, EvalRun, EvalRunDetail, EvalSummary } from "@/lib/types";

/* ── Bits ──────────────────────────────────────────────────────────── */

function Cmd({ children }: { children: string }) {
  return (
    <code className="rounded-[7px] bg-surface-2 px-2 py-1 font-mono text-[13px] text-text">
      {children}
    </code>
  );
}

function Stat({ value, caption }: { value: number | string; caption: string }) {
  return (
    <div className="rounded-[14px] bg-surface-2 p-4">
      <div className="t-numeral text-[26px]">{value}</div>
      <div className="t-caption mt-1">{caption}</div>
    </div>
  );
}

/* ── The golden set ────────────────────────────────────────────────── */

/**
 * Shown whether or not a run exists, because the dataset is the asset. The
 * code here is replaceable; a few hundred hand-reviewed questions are not.
 */
function DatasetPanel({ data }: { data: EvalDataset }) {
  if (!data.available || !data.summary) {
    return (
      <Card>
        <CardHeader
          title="Golden set"
          hint="No golden set found, or it failed validation."
        />
        <p className="text-[15px] text-muted">
          Generate candidates with <Cmd>make eval-seed</Cmd>, review every one by
          hand, then <Cmd>make eval-promote</Cmd>.
        </p>
      </Card>
    );
  }

  const { total, sql, rag, unanswerable, categories } = data.summary;
  const top = Object.entries(data.categories).slice(0, 10);
  const largest = Math.max(...top.map(([, n]) => n), 1);

  return (
    <Card>
      <CardHeader
        title="Golden set"
        hint="Hand-reviewed questions over this corpus. Every metric on this page is measured against them."
      />
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat value={total} caption="questions" />
        <Stat value={sql} caption="quantitative · SQL arm" />
        <Stat value={rag} caption="qualitative · vector arm" />
        <Stat value={unanswerable} caption="unanswerable" />
      </div>

      <p className="t-caption mt-5 mb-2.5">
        {categories} categories · the unanswerable ones are deliberate near-misses,
        and they are what makes a hallucination rate measurable at all
      </p>

      <div className="flex flex-col gap-1.5">
        {top.map(([name, n]) => (
          <div key={name} className="flex items-center gap-3">
            <span className="w-44 shrink-0 truncate font-mono text-[12.5px] text-muted">
              {name}
            </span>
            <span className="h-2 flex-1 overflow-hidden rounded-full bg-surface-2">
              <span
                className="block h-full rounded-full bg-accent/60 transition-[width] duration-1000 [transition-timing-function:var(--ease)]"
                style={{ width: `${(n / largest) * 100}%` }}
              />
            </span>
            <span className="t-caption w-6 text-right tabular-nums">{n}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}

/* ── No runs yet ───────────────────────────────────────────────────── */

function EmptyState({ dataset }: { dataset: EvalDataset | null }) {
  return (
    <div className="flex flex-col gap-5">
      <Card>
        <div className="flex flex-col items-start gap-4 sm:flex-row sm:items-center">
          <span className="flex size-11 shrink-0 items-center justify-center rounded-[14px] bg-accent-soft">
            <FlaskConical size={20} className="text-accent" strokeWidth={2} />
          </span>
          <div>
            <h3 className="t-headline">No run recorded yet</h3>
            <p className="mt-1.5 text-[15px] leading-snug text-muted">
              The harness is installed and the golden set is valid — nothing has
              been executed against it. Running one needs an LLM API key, so it
              is deliberately not something this page can trigger.
            </p>
          </div>
        </div>

        <div className="mt-6 flex flex-col gap-3 border-t border-hairline pt-5 text-[15px]">
          <div className="flex flex-wrap items-center gap-2">
            <Cmd>make eval</Cmd>
            <span className="text-muted">
              run the baseline over every question, then score it
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Cmd>make eval-grid</Cmd>
            <span className="text-muted">
              run every one-variable ablation and compare them
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Cmd>make eval-kappa</Cmd>
            <span className="text-muted">
              check the LLM judge against your own labels
            </span>
          </div>
        </div>
      </Card>

      {dataset && <DatasetPanel data={dataset} />}
    </div>
  );
}

/* ── Run picker ────────────────────────────────────────────────────── */

function RunPicker({
  runs,
  active,
  onPick,
}: {
  runs: EvalRun[];
  active: string;
  onPick: (runId: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {runs.map((run) => {
        const selected = run.run_id === active;
        return (
          <button
            key={run.run_id}
            type="button"
            onClick={() => onPick(run.run_id)}
            aria-current={selected ? "true" : undefined}
            className={cx(
              "rounded-full px-3.5 py-2 text-[13px] font-medium",
              "transition-colors duration-300",
              selected
                ? "bg-text text-bg"
                : "bg-surface-2 text-muted hover:text-text",
            )}
          >
            {run.config_name}
            <span className="ml-2 font-mono text-[11px] opacity-55">
              {run.config_hash.slice(0, 6)}
            </span>
          </button>
        );
      })}
    </div>
  );
}

/* ── Ablation grid ─────────────────────────────────────────────────── */

/**
 * One row per config, baseline first.
 *
 * Each config here moved exactly one variable, which is what makes a
 * difference in this table attributable. A grid search would fill the same
 * cells and support none of the same conclusions.
 */
function AblationTable({ runs }: { runs: EvalRun[] }) {
  const columns = METRIC_GROUPS.flatMap((g) => g.metrics).filter((metric) =>
    runs.some((run) => run.metrics[metric] !== undefined),
  );
  if (columns.length === 0) return null;

  const ordered = [...runs].sort((a, b) =>
    a.config_name === "baseline" ? -1 : b.config_name === "baseline" ? 1 : 0,
  );

  return (
    <Card>
      <CardHeader
        title="Ablation grid"
        hint="One variable changes per row. A difference here has a cause; a difference in a grid search does not."
      />
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-[14px]">
          <thead>
            <tr className="border-b border-hairline">
              <th className="t-caption px-3 py-2 text-left font-medium">config</th>
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
            {ordered.map((run) => (
              <tr key={run.run_id} className="border-b border-hairline last:border-0">
                <td className="whitespace-nowrap px-3 py-2.5">
                  <span className="font-medium">{run.config_name}</span>
                  {run.config_name === "baseline" && (
                    <span className="t-caption ml-2">reference</span>
                  )}
                </td>
                {columns.map((metric) => {
                  const value = run.metrics[metric];
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
                          "inline-block min-w-[56px] rounded-[8px] px-2 py-1 tabular-nums",
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

/* ── Run header ────────────────────────────────────────────────────── */

function RunHeader({ detail }: { detail: EvalRunDetail }) {
  const settings = Object.entries(detail.config);
  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h3 className="t-headline">{detail.config_name}</h3>
          <p className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[13px] text-muted">
            <span className="font-mono">{detail.run_id}</span>
            <span className="inline-flex items-center gap-1">
              <GitCommitHorizontal size={13} />
              <span className="font-mono">{detail.git_sha || "unknown"}</span>
            </span>
            {detail.git_dirty && (
              <span className="rounded-full bg-warn-soft px-2 py-0.5 text-[11px] font-medium text-warn">
                tree was dirty
              </span>
            )}
            <span>{new Date(detail.started_at).toLocaleString()}</span>
          </p>
        </div>
        <div className="flex gap-2">
          <span className="rounded-[10px] bg-surface-2 px-3 py-2 text-center">
            <span className="t-numeral block text-[17px]">{detail.counts.traces}</span>
            <span className="t-caption">questions</span>
          </span>
          <span className="rounded-[10px] bg-surface-2 px-3 py-2 text-center">
            <span className="t-numeral block text-[17px]">{detail.counts.fallbacks}</span>
            <span className="t-caption">fallbacks</span>
          </span>
        </div>
      </div>

      {settings.length > 0 && (
        <div className="mt-5 flex flex-wrap gap-1.5 border-t border-hairline pt-5">
          {settings.map(([key, value]) => (
            <span
              key={key}
              className="rounded-[8px] bg-surface-2 px-2.5 py-1 font-mono text-[12px] text-muted"
            >
              {key}=<span className="text-text">{value}</span>
            </span>
          ))}
        </div>
      )}
    </Card>
  );
}

/* ── The tab ───────────────────────────────────────────────────────── */

export function Evals() {
  const [summary, setSummary] = useState<EvalSummary | null>(null);
  const [dataset, setDataset] = useState<EvalDataset | null>(null);
  const [detail, setDetail] = useState<EvalRunDetail | null>(null);
  const [active, setActive] = useState<string>("");
  const [error, setError] = useState<string>("");

  useEffect(() => {
    const ctrl = new AbortController();
    Promise.all([getEvalSummary(ctrl.signal), getEvalDataset(ctrl.signal)])
      .then(([s, d]) => {
        setSummary(s);
        setDataset(d);
        if (s.runs.length > 0) setActive(s.runs[0].run_id);
      })
      .catch((e: Error) => {
        if (e.name !== "AbortError") setError(e.message);
      });
    return () => ctrl.abort();
  }, []);

  useEffect(() => {
    if (!active) return;
    const ctrl = new AbortController();
    getEvalRun(active, ctrl.signal)
      .then(setDetail)
      .catch((e: Error) => {
        if (e.name !== "AbortError") setError(e.message);
      });
    return () => ctrl.abort();
  }, [active]);

  if (error) {
    return (
      <div className="py-16">
        <ErrorNote
          message={`Couldn't load eval results: ${error}. Is the backend running?`}
        />
      </div>
    );
  }

  if (!summary) {
    return (
      <div className="flex flex-col gap-5 py-10">
        <Skeleton className="h-36" />
        <Skeleton className="h-64" />
      </div>
    );
  }

  return (
    <div className="py-10">
      <Reveal>
        <header className="mb-7">
          <p className="t-eyebrow mb-2">Evaluation</p>
          <h2 className="t-title">Does this system actually work?</h2>
          <p className="t-intro mt-3 max-w-2xl">
            Four metric surfaces over a hand-reviewed golden set. Three of the
            four are deterministic, so most of what you see here carries no
            model variance at all.
          </p>
        </header>
      </Reveal>

      {!summary.has_data ? (
        <Reveal delay={60}>
          <EmptyState dataset={dataset} />
        </Reveal>
      ) : (
        <div className="flex flex-col gap-5">
          {summary.runs.length > 1 && (
            <Reveal delay={40}>
              <AblationTable runs={summary.runs} />
            </Reveal>
          )}

          <Reveal delay={60}>
            <RunPicker runs={summary.runs} active={active} onPick={setActive} />
          </Reveal>

          {!detail ? (
            <Skeleton className="h-64" />
          ) : (
            <>
              <Reveal delay={80}>
                <RunHeader detail={detail} />
              </Reveal>

              <Reveal delay={100}>
                <MetricGroups metrics={detail.metrics} />
              </Reveal>

              <Reveal delay={120}>
                <div className="rounded-[18px] bg-accent-soft p-5">
                  <p className="flex items-start gap-2.5 text-[14px] leading-relaxed text-text">
                    <ShieldCheck size={17} className="mt-0.5 shrink-0 text-accent" />
                    <span>
                      The judged metrics — faithfulness, relevance and
                      correctness — mean nothing until the judge is checked
                      against human labels. Run <Cmd>make eval-kappa</Cmd> and
                      report that number next to them, whatever it turns out to
                      be.
                    </span>
                  </p>
                </div>
              </Reveal>

              <Reveal delay={140}>
                <ConfusionMatrix confusion={detail.confusion} />
              </Reveal>

              <Reveal delay={160}>
                <SliceTable
                  title="By category"
                  hint="Aggregates hide the interesting failures. This is where they surface."
                  slices={detail.by_category}
                />
              </Reveal>

              <Reveal delay={180}>
                <Failures failures={detail.failures} />
              </Reveal>

              {dataset && (
                <Reveal delay={200}>
                  <DatasetPanel data={dataset} />
                </Reveal>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
