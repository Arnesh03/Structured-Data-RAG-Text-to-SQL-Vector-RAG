/**
 * One categorical palette for every chart in the app.
 *
 * The hues are mid-tone on purpose: each one clears contrast against both the
 * light and the dark surface, so charts don't need a second theme-specific set.
 */
export const PALETTE = [
  "#0071e3", // blue
  "#a259ff", // purple
  "#f56300", // orange
  "#00a1a7", // teal
  "#e0218a", // pink
  "#5e5ce6", // indigo
  "#00845a", // green
  "#b25000", // amber
];

export const color = (i: number) => PALETTE[i % PALETTE.length];

/** Semantic colors for values that mean the same thing wherever they appear. */
export const SEMANTIC: Record<string, string> = {
  Emergency: "#e0218a",
  Urgent: "#f56300",
  Elective: "#0071e3",
  Normal: "#00a1a7",
  Abnormal: "#e0218a",
  Inconclusive: "#8e8e93",
  Male: "#0071e3",
  Female: "#a259ff",
};

export const seriesColor = (name: string, i: number) => SEMANTIC[name] ?? color(i);

/** Axis and grid styling shared by every chart, driven by the theme tokens. */
export const AXIS = {
  stroke: "var(--chart-axis)",
  fontSize: 11,
  tickLine: false,
  axisLine: false,
} as const;

export const GRID = {
  stroke: "var(--chart-grid)",
  strokeDasharray: "3 3",
  vertical: false,
} as const;

export const TOOLTIP_STYLE = {
  contentStyle: {
    background: "var(--bg-elevated)",
    border: "1px solid var(--hairline)",
    borderRadius: 14,
    fontSize: 13,
    padding: "10px 14px",
    boxShadow: "var(--shadow-lg)",
    color: "var(--text)",
  },
  labelStyle: { color: "var(--text-3)", fontSize: 12, marginBottom: 5 },
  cursor: { fill: "var(--surface-2)" },
} as const;

/**
 * Recharts hands tooltip formatters a loosely typed value and series key.
 * This narrows both once, so each chart can write a plain
 * `(value: number, key: string) => [text, label]` formatter.
 */
type RechartsValue = number | string | ReadonlyArray<number | string> | undefined;
type RechartsName = number | string | undefined;

export function tooltipFormat(fn: (value: number, key: string) => [string, string]) {
  return (value: RechartsValue, name: RechartsName): [string, string] =>
    fn(Number(Array.isArray(value) ? value[0] : value), String(name ?? ""));
}
