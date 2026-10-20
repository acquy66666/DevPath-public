"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { formatAmount } from "@/lib/format";
import { cn } from "@/lib/utils";

/**
 * Pieces every admin money page shares: the date range, and how a sum, a
 * change and a bucket are written.
 *
 * Dates are Vietnamese calendar days as "YYYY-MM-DD" strings end to end --
 * the API takes and returns them that way, and a `Date` in the browser's
 * zone would move them by a day west of Greenwich.
 */

const VIETNAM_DAY = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Asia/Ho_Chi_Minh",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

export function vietnamToday(): string {
  return VIETNAM_DAY.format(new Date());
}

export function addDays(day: string, days: number): string {
  const [y, m, d] = day.split("-").map(Number);
  const moved = new Date(Date.UTC(y, m - 1, d + days));
  return moved.toISOString().slice(0, 10);
}

export function daysBetween(start: string, end: string): number {
  const toUtc = (day: string) => {
    const [y, m, d] = day.split("-").map(Number);
    return Date.UTC(y, m - 1, d);
  };
  return Math.round((toUtc(end) - toUtc(start)) / 86_400_000) + 1;
}

export interface DateRange {
  start: string;
  end: string;
}

export function presetRanges(today: string): { label: string; range: DateRange }[] {
  const year = today.slice(0, 4);
  return [
    { label: "Hôm nay", range: { start: today, end: today } },
    { label: "7 ngày", range: { start: addDays(today, -6), end: today } },
    { label: "30 ngày", range: { start: addDays(today, -29), end: today } },
    { label: "90 ngày", range: { start: addDays(today, -89), end: today } },
    { label: "Năm nay", range: { start: `${year}-01-01`, end: today } },
    { label: "12 tháng", range: { start: addDays(today, -364), end: today } },
  ];
}

/** Two date inputs and the usual presets. */
export function DateRangePicker({
  value,
  onChange,
}: {
  value: DateRange;
  onChange: (range: DateRange) => void;
}) {
  const today = vietnamToday();
  return (
    <div className="flex flex-wrap items-end gap-3">
      <div className="space-y-1">
        <Label htmlFor="range-start" className="text-xs">
          Từ ngày
        </Label>
        <Input
          id="range-start"
          type="date"
          value={value.start}
          max={value.end}
          onChange={(event) =>
            event.target.value && onChange({ ...value, start: event.target.value })
          }
          className="h-9 w-40"
        />
      </div>
      <div className="space-y-1">
        <Label htmlFor="range-end" className="text-xs">
          Đến ngày
        </Label>
        <Input
          id="range-end"
          type="date"
          value={value.end}
          min={value.start}
          onChange={(event) => event.target.value && onChange({ ...value, end: event.target.value })}
          className="h-9 w-40"
        />
      </div>
      <div role="group" aria-label="Khoảng có sẵn" className="flex flex-wrap gap-1">
        {presetRanges(today).map((preset) => {
          const active = preset.range.start === value.start && preset.range.end === value.end;
          return (
            <button
              key={preset.label}
              type="button"
              aria-pressed={active}
              onClick={() => onChange(preset.range)}
              className={cn(
                "h-9 rounded-md border px-2.5 text-xs transition-colors focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none",
                active
                  ? "border-primary bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {preset.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/** "1.234.000 ₫" -- zero stays "0 ₫". */
export function money(value: string | number): string {
  return formatAmount(String(value));
}

const DATE = new Intl.DateTimeFormat("vi-VN", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  timeZone: "UTC",
});

export function day(isoDate: string): string {
  const [y, m, d] = isoDate.slice(0, 10).split("-").map(Number);
  return DATE.format(new Date(Date.UTC(y, m - 1, d)));
}

/** A bucket start ("2026-10-20T09:00:00", Vietnamese wall clock), as words. */
export function bucketName(bucket: string, granularity: string): { tick: string; label: string } {
  const [datePart, timePart = "00:00"] = bucket.split("T");
  const [y, m, d] = datePart.split("-").map(Number);
  const dd = String(d).padStart(2, "0");
  const mm = String(m).padStart(2, "0");
  switch (granularity) {
    case "hour": {
      const hour = timePart.slice(0, 2);
      return { tick: `${hour}h`, label: `${hour}:00 ngày ${dd}/${mm}/${y}` };
    }
    case "day":
      return { tick: `${dd}/${mm}`, label: `${dd}/${mm}/${y}` };
    case "week":
      return { tick: `${dd}/${mm}`, label: `Tuần từ ${dd}/${mm}/${y}` };
    case "month":
      return { tick: `${mm}/${String(y % 100).padStart(2, "0")}`, label: `Tháng ${m}/${y}` };
    case "quarter": {
      const quarter = Math.floor((m - 1) / 3) + 1;
      return { tick: `Q${quarter}/${String(y % 100).padStart(2, "0")}`, label: `Quý ${quarter}/${y}` };
    }
    default:
      return { tick: String(y), label: `Năm ${y}` };
  }
}

/** A small table cell for money, right-aligned in tabular figures. */
export function MoneyCell({ value, muted }: { value: string; muted?: boolean }) {
  return (
    <td className={cn("px-3 py-2 text-right tabular-nums", muted && "text-muted-foreground")}>
      {money(value)}
    </td>
  );
}
