const compact = new Intl.NumberFormat("en-US", {
  notation: "compact",
  maximumFractionDigits: 1,
});

export const num = (v: number) => v.toLocaleString("en-US");

export const compactNum = (v: number) => compact.format(v);

export const usd = (v: number, decimals = 0) =>
  v.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });

export const compactUsd = (v: number) => `$${compact.format(v)}`;

/** '2023-07' -> 'Jul 23', for axis ticks that have to stay narrow. */
export const monthLabel = (iso: string) => {
  const [year, month] = iso.split("-");
  const name = new Date(Number(year), Number(month) - 1).toLocaleString("en-US", {
    month: "short",
  });
  return `${name} ${year.slice(2)}`;
};

export const titleCase = (s: string) =>
  s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

/** Numbers get right-aligned tabular cells; text stays left. */
export const isNumeric = (v: unknown): v is number =>
  typeof v === "number" && Number.isFinite(v);
