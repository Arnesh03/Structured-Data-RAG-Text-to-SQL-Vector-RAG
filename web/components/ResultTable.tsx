"use client";

import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { BarChart3, Table2 } from "lucide-react";
import { AXIS, GRID, TOOLTIP_STYLE, seriesColor, tooltipFormat } from "@/lib/chart";
import { compactNum, isNumeric, titleCase } from "@/lib/format";
import { cx } from "./ui";

type Cell = string | number | null;

/**
 * A query result is worth charting when it reads as a series: one label
 * column, at least one measure, and few enough rows that bars stay legible.
 */
function chartable(columns: string[], rows: Cell[][]) {
  if (rows.length < 2 || rows.length > 25 || columns.length < 2) return null;
  if (isNumeric(rows[0][0])) return null;
  const valueIndex = rows[0].findIndex((v, i) => i > 0 && isNumeric(v));
  return valueIndex === -1 ? null : valueIndex;
}

export function ResultTable({
  columns,
  rows,
}: {
  columns: string[];
  rows: Cell[][];
}) {
  const valueIndex = useMemo(() => chartable(columns, rows), [columns, rows]);
  const [view, setView] = useState<"table" | "chart">("table");
  const showChart = valueIndex !== null && view === "chart";

  const data = useMemo(
    () =>
      valueIndex === null
        ? []
        : rows.map((r) => ({
            name: String(r[0]),
            value: Number(r[valueIndex]),
          })),
    [rows, valueIndex],
  );

  if (!columns.length) return null;

  return (
    <div className="overflow-hidden rounded-2xl bg-surface ring-1 ring-hairline">
      <div className="flex items-center justify-between gap-2 border-b border-hairline px-4 py-2.5">
        <span className="text-[12px] font-medium text-muted">
          {rows.length} {rows.length === 1 ? "row" : "rows"}
        </span>
        {valueIndex !== null && (
          <div className="flex rounded-full bg-surface-2 p-0.5">
            {(["table", "chart"] as const).map((v) => {
              const Icon = v === "table" ? Table2 : BarChart3;
              return (
                <button
                  key={v}
                  type="button"
                  onClick={() => setView(v)}
                  aria-pressed={view === v}
                  aria-label={`Show as ${v}`}
                  className={cx(
                    "rounded-full px-2.5 py-1.5 transition duration-300",
                    view === v
                      ? "bg-surface text-text shadow-[var(--shadow-sm)]"
                      : "text-faint hover:text-muted",
                  )}
                >
                  <Icon size={13} />
                </button>
              );
            })}
          </div>
        )}
      </div>

      {showChart ? (
        <div className="h-60 p-4 pr-5">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 4, right: 4, left: -8, bottom: 0 }}>
              <CartesianGrid {...GRID} />
              <XAxis
                dataKey="name"
                {...AXIS}
                interval={0}
                angle={data.length > 6 ? -30 : 0}
                textAnchor={data.length > 6 ? "end" : "middle"}
                height={data.length > 6 ? 58 : 24}
              />
              <YAxis {...AXIS} tickFormatter={compactNum} width={48} />
              <Tooltip
                {...TOOLTIP_STYLE}
                formatter={tooltipFormat((v) => [
                  v.toLocaleString("en-US"),
                  titleCase(columns[valueIndex]),
                ])}
              />
              <Bar dataKey="value" radius={[8, 8, 0, 0]} maxBarSize={54} isAnimationActive={false}>
                {data.map((d, i) => (
                  <Cell key={d.name} fill={seriesColor(d.name, i)} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="max-h-80 overflow-auto">
          <table className="w-full text-[13.5px]">
            <thead className="sticky top-0 bg-surface-2 text-[11px] uppercase tracking-wide text-faint">
              <tr>
                {columns.map((c) => (
                  <th key={c} className="whitespace-nowrap px-4 py-2.5 text-left font-medium">
                    {titleCase(c)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={i} className="border-t border-hairline">
                  {row.map((cell, j) => (
                    <td
                      key={j}
                      className={cx(
                        "whitespace-nowrap px-4 py-2",
                        isNumeric(cell)
                          ? "text-right font-mono tabular-nums"
                          : "text-muted",
                      )}
                    >
                      {cell === null
                        ? "—"
                        : isNumeric(cell)
                          ? cell.toLocaleString("en-US")
                          : String(cell)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
