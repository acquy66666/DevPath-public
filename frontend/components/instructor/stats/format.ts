/**
 * Formatting for the dashboard's buckets and ratios.
 *
 * Buckets arrive as date-only strings ("2026-09-24") on the Vietnamese
 * calendar. `new Date("2026-09-24")` would read that as UTC midnight and then
 * print it in the browser's zone -- the day before, anywhere west of
 * Greenwich -- so they are built and printed in UTC, where the date is exactly
 * the date that was sent.
 */

const WEEKDAY_DATE = new Intl.DateTimeFormat("vi-VN", {
  weekday: "long",
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  timeZone: "UTC",
});

const DATE = new Intl.DateTimeFormat("vi-VN", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  timeZone: "UTC",
});

const PERCENT = new Intl.NumberFormat("vi-VN", {
  style: "percent",
  maximumFractionDigits: 1,
});

/** "1,2 Tr", "500 N": short enough for an axis, and Vietnamese. */
const COMPACT = new Intl.NumberFormat("vi-VN", {
  notation: "compact",
  maximumFractionDigits: 1,
});

const COUNT = new Intl.NumberFormat("vi-VN");

function parts(bucket: string): [number, number, number] {
  const [year, month, day] = bucket.split("-").map(Number);
  return [year, month, day];
}

function utc(bucket: string): Date {
  const [year, month, day] = parts(bucket);
  return new Date(Date.UTC(year, month - 1, day));
}

export function bucketTick(bucket: string, granularity: "day" | "month"): string {
  const [year, month, day] = parts(bucket);
  const mm = String(month).padStart(2, "0");
  return granularity === "day"
    ? `${String(day).padStart(2, "0")}/${mm}`
    : `${mm}/${String(year % 100).padStart(2, "0")}`;
}

export function bucketLabel(bucket: string, granularity: "day" | "month"): string {
  if (granularity === "day") return WEEKDAY_DATE.format(utc(bucket));
  const [year, month] = parts(bucket);
  return `Tháng ${month}/${year}`;
}

export function formatDay(isoDate: string): string {
  return DATE.format(utc(isoDate));
}

/** A ratio from the API; `null` means nobody to measure, never 0 %. */
export function formatRate(rate: number | null): string {
  return rate === null ? "—" : PERCENT.format(rate);
}

export function formatCompact(value: number): string {
  return COMPACT.format(value);
}

export function formatCount(value: number): string {
  return COUNT.format(value);
}

/**
 * How the period compares with the one before it, or null when there is no
 * honest percentage: from zero, any growth is infinite.
 */
export function change(current: number, previous: number): number | null {
  if (previous === 0) return null;
  return (current - previous) / previous;
}
