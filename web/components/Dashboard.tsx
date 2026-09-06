"use client";

import { useEffect, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { dashboardOnce } from "@/lib/api";
import {
  AXIS,
  GRID,
  TOOLTIP_STYLE,
  color,
  seriesColor,
  tooltipFormat,
} from "@/lib/chart";
import { compactNum, compactUsd, monthLabel, num, usd } from "@/lib/format";
import type { Dashboard as DashboardData, Series } from "@/lib/types";
import { Card, CardHeader, CountUp, ErrorNote, Reveal, Skeleton } from "./ui";
/*
  Charts do not animate themselves. Reveal already fades each card in, and a
  second motion system on top of it is both redundant and fragile: Recharts
  drives its entry animation with requestAnimationFrame, which a throttled or
  unpainted renderer (a background tab, a slow first paint) can stall - leaving
  bars and arcs frozen at their zero-size first frame.
*/

/** A headline figure, sized to be read from across the room. */
function BigStat({
  value,
  label,
  sub,
  format,
  delay,
}: {
  value: number;
  label: string;
  sub?: string;
  format?: (n: number) => string;
  delay: number;
}) {
  return (
    <Reveal delay={delay} className="text-center">
      <p className="t-numeral text-[clamp(2.25rem,4.5vw,3.5rem)]">
        <CountUp value={value} format={format} />
      </p>
      <p className="mt-1 text-[15px] font-medium">{label}</p>
      {sub && <p className="t-caption mt-0.5">{sub}</p>}
    </Reveal>
  );
}

function Donut({ data, unit = "admissions" }: { data: Series[]; unit?: string }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <PieChart>
        <Pie
          data={data}
          dataKey="admissions"
          nameKey="name"
          innerRadius="58%"
          outerRadius="84%"
          paddingAngle={2}
          stroke="var(--surface)"
          strokeWidth={3}
          isAnimationActive={false}
        >
          {data.map((d, i) => (
            <Cell key={d.name} fill={seriesColor(d.name, i)} />
          ))}
        </Pie>
        <Tooltip {...TOOLTIP_STYLE} formatter={tooltipFormat((v) => [num(v), unit])} />
        <Legend
          verticalAlign="bottom"
          height={30}
          iconType="circle"
          iconSize={8}
          formatter={(value) => (
            <span style={{ color: "var(--text-2)", fontSize: 13 }}>{value}</span>
          )}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}

export function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    dashboardOnce()
      .then((d) => live && setData(d))
      .catch((e) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, []);

  if (error) return <div className="py-24"><ErrorNote message={`Could not load analytics: ${error}`} /></div>;

  if (!data) {
    return (
      <div className="space-y-5 py-16">
        <Skeleton className="h-32" />
        <Skeleton className="h-80" />
        <div className="grid gap-5 lg:grid-cols-3">
          <Skeleton className="h-72 lg:col-span-2" />
          <Skeleton className="h-72" />
        </div>
      </div>
    );
  }

  const k = data.kpis;
  const months = data.by_month.map((m) => ({ ...m, label: monthLabel(String(m.name)) }));

  return (
    <div className="pb-10">
      {/* Headline figures */}
      <section className="pt-14 sm:pt-20">
        <Reveal className="mx-auto mb-12 max-w-2xl text-center sm:mb-16">
          <p className="t-eyebrow mb-3">Analytics</p>
          <h2 className="t-title text-balance">Five years of admissions, at a glance</h2>
          <p className="t-intro mt-4">
            Every figure below is a live SQL aggregate over the cleaned table —
            the same data the chat queries.
          </p>
        </Reveal>

        <div className="grid grid-cols-2 gap-10 sm:grid-cols-4">
          <BigStat value={k.total_admissions} label="Admissions" delay={0} />
          <BigStat value={k.unique_patients} label="Patients" sub={`avg age ${k.avg_age}`} delay={70} />
          <BigStat
            value={k.total_billing}
            label="Billed"
            sub={`${usd(k.avg_billing)} average`}
            format={(n) => `$${(n / 1e9).toFixed(2)}B`}
            delay={140}
          />
          <BigStat
            value={k.avg_stay_days}
            label="Days"
            sub="average stay"
            format={(n) => n.toFixed(1)}
            delay={210}
          />
        </div>

        <Reveal delay={280}>
          <p className="t-caption mt-8 text-center">
            {k.first_admission} → {k.last_admission} · {k.emergency_share}% arrived
            through the emergency department · {k.abnormal_share}% had abnormal
            test results
          </p>
        </Reveal>
      </section>

      {/* Time series */}
      <Reveal className="mt-14 sm:mt-20">
        <Card>
          <CardHeader
            title="Admissions over time"
            hint="Monthly volume across the full record window"
          />
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={months} margin={{ top: 4, right: 8, left: -4, bottom: 0 }}>
                <defs>
                  <linearGradient id="admGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={color(0)} stopOpacity={0.28} />
                    <stop offset="100%" stopColor={color(0)} stopOpacity={0.01} />
                  </linearGradient>
                </defs>
                <CartesianGrid {...GRID} />
                <XAxis dataKey="label" {...AXIS} minTickGap={30} />
                <YAxis {...AXIS} tickFormatter={compactNum} width={46} />
                <Tooltip
                  {...TOOLTIP_STYLE}
                  cursor={{ stroke: "var(--chart-axis)", strokeDasharray: "4 4" }}
                  formatter={tooltipFormat((v, key) =>
                    key === "billing" ? [usd(v), "Billed"] : [num(v), "Admissions"],
                  )}
                />
                <Area
                  type="monotone"
                  dataKey="admissions"
                  stroke={color(0)}
                  strokeWidth={2.5}
                  fill="url(#admGrad)"
                  isAnimationActive={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </Reveal>

      <div className="mt-5 grid gap-5 lg:grid-cols-3">
        <Reveal className="lg:col-span-2">
          <Card className="h-full">
            <CardHeader
              title="Medical conditions"
              hint="Admission count per condition, with average billing in the tooltip"
            />
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={data.by_condition}
                  layout="vertical"
                  margin={{ top: 0, right: 16, left: 12, bottom: 0 }}
                >
                  <CartesianGrid {...GRID} vertical horizontal={false} />
                  <XAxis type="number" {...AXIS} tickFormatter={compactNum} />
                  <YAxis type="category" dataKey="name" {...AXIS} width={100} />
                  <Tooltip
                    {...TOOLTIP_STYLE}
                    formatter={tooltipFormat((v, key) =>
                      key === "admissions"
                        ? [num(v), "Admissions"]
                        : [usd(v), "Avg billing"],
                    )}
                  />
                  <Bar dataKey="admissions" radius={[0, 8, 8, 0]} maxBarSize={26} isAnimationActive={false}>
                    {data.by_condition.map((d, i) => (
                      <Cell key={d.name} fill={color(i)} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </Reveal>

        <Reveal delay={90}>
          <Card className="h-full">
            <CardHeader title="Admission type" hint="How patients arrive" />
            <div className="h-72">
              <Donut data={data.by_admission_type} />
            </div>
          </Card>
        </Reveal>
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-3">
        <Reveal>
          <Card className="h-full">
            <CardHeader title="Test results" hint="Summary finding per admission" />
            <div className="h-64">
              <Donut data={data.by_test_result} />
            </div>
          </Card>
        </Reveal>

        <Reveal delay={90} className="lg:col-span-2">
          <Card className="h-full">
            <CardHeader
              title="Average billing by insurer"
              hint="Mean charge per admission, by insurance provider"
            />
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.by_insurance} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid {...GRID} />
                  <XAxis dataKey="name" {...AXIS} interval={0} />
                  <YAxis
                    {...AXIS}
                    width={56}
                    tickFormatter={(v: number) => compactUsd(v)}
                    domain={[0, "dataMax"]}
                  />
                  <Tooltip
                    {...TOOLTIP_STYLE}
                    formatter={tooltipFormat((v, key) =>
                      key === "avg_billing"
                        ? [usd(v, 2), "Avg billing"]
                        : [num(v), "Admissions"],
                    )}
                  />
                  <Bar dataKey="avg_billing" radius={[8, 8, 0, 0]} maxBarSize={58} isAnimationActive={false}>
                    {data.by_insurance.map((d, i) => (
                      <Cell key={d.name} fill={color(i + 1)} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </Reveal>
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <Reveal>
          <Card className="h-full">
            <CardHeader title="Age groups" hint="Admissions by patient age band" />
            <div className="h-60">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.by_age_group} margin={{ top: 4, right: 8, left: -4, bottom: 0 }}>
                  <CartesianGrid {...GRID} />
                  <XAxis dataKey="name" {...AXIS} interval={0} />
                  <YAxis {...AXIS} tickFormatter={compactNum} width={46} />
                  <Tooltip {...TOOLTIP_STYLE} formatter={tooltipFormat((v) => [num(v), "Admissions"])} />
                  <Bar dataKey="admissions" radius={[8, 8, 0, 0]} maxBarSize={50} isAnimationActive={false}>
                    {data.by_age_group.map((d, i) => (
                      <Cell key={d.name} fill={color(i)} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </Reveal>

        <Reveal delay={90}>
          <Card className="h-full">
            <CardHeader title="Average length of stay" hint="Mean days in hospital, by condition" />
            <div className="h-60">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.stay_by_condition} margin={{ top: 4, right: 8, left: -8, bottom: 0 }}>
                  <CartesianGrid {...GRID} />
                  <XAxis dataKey="name" {...AXIS} interval={0} angle={-20} height={46} textAnchor="end" />
                  <YAxis {...AXIS} width={38} unit="d" domain={[0, "dataMax + 2"]} />
                  <Tooltip {...TOOLTIP_STYLE} formatter={tooltipFormat((v) => [`${v} days`, "Avg stay"])} />
                  <Bar dataKey="avg_stay" radius={[8, 8, 0, 0]} maxBarSize={46} isAnimationActive={false}>
                    {data.stay_by_condition.map((d, i) => (
                      <Cell key={d.name} fill={color(i)} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </Reveal>
      </div>
    </div>
  );
}
