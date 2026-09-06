"use client";

import { useEffect, useState } from "react";
import { ArrowRight, CircleCheck } from "lucide-react";
import { getPreprocessing, getSchema } from "@/lib/api";
import { num, titleCase } from "@/lib/format";
import type { PreprocessingReport, SchemaColumn } from "@/lib/types";
import { Badge, Card, CardHeader, CountUp, ErrorNote, Reveal, Skeleton, cx } from "./ui";

/** The counters a step reports, rendered as chips so the audit is scannable. */
function stepCounts(step: PreprocessingReport["steps"][number]) {
  const chips: { label: string; tone: "neutral" | "warn" | "accent" }[] = [];
  if (step.rows_dropped) {
    chips.push({ label: `${num(step.rows_dropped)} rows dropped`, tone: "warn" });
  }
  if (step.values_changed) {
    chips.push({ label: `${num(step.values_changed)} values rewritten`, tone: "accent" });
  }
  if (step.columns_added) {
    chips.push({ label: `${step.columns_added} columns added`, tone: "accent" });
  }
  if (step.unique_patients) {
    chips.push({ label: `${num(step.unique_patients)} unique patients`, tone: "neutral" });
  }
  if (Object.keys(step.unexpected_values ?? {}).length > 0) {
    chips.push({ label: "unexpected categories found", tone: "warn" });
  }
  return chips;
}

export function DataView() {
  const [report, setReport] = useState<PreprocessingReport | null>(null);
  const [schema, setSchema] = useState<SchemaColumn[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    Promise.all([getPreprocessing(ctrl.signal), getSchema(ctrl.signal)])
      .then(([r, s]) => {
        setReport(r);
        setSchema(s.columns);
      })
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      });
    return () => ctrl.abort();
  }, []);

  if (error) {
    return <div className="py-24"><ErrorNote message={`Could not load data details: ${error}`} /></div>;
  }

  if (!report || !schema) {
    return (
      <div className="grid gap-5 py-16 lg:grid-cols-5">
        <Skeleton className="h-[560px] lg:col-span-3" />
        <Skeleton className="h-[560px] lg:col-span-2" />
      </div>
    );
  }

  const kept = report.rows_out / report.rows_in;

  return (
    <div className="pb-10">
      <section className="pt-14 sm:pt-20">
        <Reveal className="mx-auto mb-12 max-w-2xl text-center sm:mb-16">
          <p className="t-eyebrow mb-3">Preprocessing</p>
          <h2 className="t-title text-balance">Nothing changed without a record of it</h2>
          <p className="t-intro mt-4">
            The raw file arrives with scrambled names, stray punctuation,
            duplicate rows and negative charges. Every repair is counted.
          </p>
        </Reveal>

        {/* Row funnel */}
        <Reveal>
          <div className="mx-auto flex max-w-2xl items-center justify-center gap-8 sm:gap-14">
            <div className="text-center">
              <p className="t-numeral text-[clamp(1.75rem,3.4vw,2.75rem)] text-muted">
                <CountUp value={report.rows_in} />
              </p>
              <p className="t-caption mt-1">Raw rows</p>
            </div>
            <ArrowRight size={22} className="shrink-0 text-faint" />
            <div className="text-center">
              <p className="t-numeral text-[clamp(1.75rem,3.4vw,2.75rem)] text-accent">
                <CountUp value={report.rows_out} />
              </p>
              <p className="t-caption mt-1">Clean rows</p>
            </div>
            <div className="text-center">
              <p className="t-numeral text-[clamp(1.75rem,3.4vw,2.75rem)]">
                <CountUp value={kept * 100} format={(n) => `${n.toFixed(1)}%`} />
              </p>
              <p className="t-caption mt-1">Retained</p>
            </div>
          </div>
        </Reveal>
      </section>

      <div className="mt-12 grid gap-5 lg:grid-cols-5">
        <Reveal className="lg:col-span-3">
          <Card className="h-full">
            <CardHeader
              title="Cleaning pipeline"
              hint="Each transformation applied to the raw CSV, in order"
              action={<Badge tone="accent">{report.steps.length} steps</Badge>}
            />
            <ol className="relative space-y-6 border-l border-hairline pl-6">
              {report.steps.map((step) => (
                <li key={step.step} className="relative">
                  <span className="absolute -left-[30px] top-1.5 size-2.5 rounded-full bg-accent ring-4 ring-surface" />
                  <p className="font-mono text-[13px] font-medium">{step.step}</p>
                  <p className="mt-1 text-[15px] leading-relaxed text-muted">
                    {step.detail}
                  </p>
                  {stepCounts(step).length > 0 && (
                    <div className="mt-2.5 flex flex-wrap gap-2">
                      {stepCounts(step).map((c) => (
                        <Badge key={c.label} tone={c.tone}>{c.label}</Badge>
                      ))}
                    </div>
                  )}
                </li>
              ))}
              <li className="relative">
                <span className="absolute -left-[30px] top-1.5 size-2.5 rounded-full bg-accent ring-4 ring-surface" />
                <p className="flex items-center gap-1.5 text-[13px] font-medium text-accent">
                  <CircleCheck size={14} />
                  Loaded into SQLite
                </p>
                <p className="mt-1 text-[15px] leading-relaxed text-muted">
                  {num(report.rows_out)} rows across {report.columns_out.length} columns,
                  indexed on condition, admission type, date, month, insurer,
                  hospital, patient and test result.
                </p>
              </li>
            </ol>
          </Card>
        </Reveal>

        <div className="space-y-5 lg:col-span-2">
          <Reveal delay={90}>
            <Card>
              <CardHeader title="Dataset summary" hint="After cleaning" />
              <dl className="grid grid-cols-2 gap-x-6 gap-y-5">
                {[
                  ["Unique patients", num(report.summary.unique_patients)],
                  ["Hospitals", num(report.summary.unique_hospitals)],
                  ["Physicians", num(report.summary.unique_doctors)],
                  ["Median stay", `${report.summary.median_stay_days} days`],
                  ["First admission", report.summary.date_range[0]],
                  ["Last admission", report.summary.date_range[1]],
                ].map(([label, value]) => (
                  <div key={label}>
                    <dt className="t-caption">{label}</dt>
                    <dd className="mt-1 font-mono text-[17px] tabular-nums">{value}</dd>
                  </div>
                ))}
              </dl>
            </Card>
          </Reveal>

          <Reveal delay={160}>
            <Card padded={false} className="overflow-hidden">
              <div className="p-6 pb-4 sm:p-7 sm:pb-4">
                <CardHeader
                  title="Table schema"
                  hint="What the Text-to-SQL prompt sees"
                  action={<Badge tone="sql">{schema.length} columns</Badge>}
                />
              </div>
              <div className="max-h-[440px] overflow-y-auto border-t border-hairline">
                <table className="w-full text-[13px]">
                  <tbody>
                    {schema.map((col, i) => (
                      <tr key={col.name} className={cx(i > 0 && "border-t border-hairline")}>
                        <td className="whitespace-nowrap px-6 py-3 align-top font-mono font-medium">
                          {col.name}
                        </td>
                        <td className="whitespace-nowrap px-2 py-3 align-top text-[10px] uppercase tracking-wide text-faint">
                          {col.type}
                        </td>
                        <td className="px-6 py-3 align-top leading-relaxed text-muted">
                          {col.description || titleCase(col.name)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          </Reveal>
        </div>
      </div>
    </div>
  );
}
