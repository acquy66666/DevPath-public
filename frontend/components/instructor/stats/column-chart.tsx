"use client";

import { useId, useState, type KeyboardEvent } from "react";

import { cn } from "@/lib/utils";

export interface Column {
  key: string;
  /** Under the axis, when there is room for it: "24/09", "09/26". */
  tick: string;
  /** In the tooltip and the table: "Thứ Năm, 24/09/2026". */
  label: string;
  value: number;
  /** The value as the reader should see it: "280.000 ₫", "3 học viên". */
  display: string;
  /** A second, quieter line in the tooltip. */
  detail?: string;
}

/** Axis labels that fit side by side at phone width without touching. */
const MAX_TICKS = 7;
const TARGET_GRIDLINES = 4;

/**
 * Round the top of the scale up to a clean number (1, 2 or 5 × 10ⁿ per step),
 * so the gridlines read 0 / 100 N / 200 N rather than 0 / 93.333 / 186.667.
 * Counts never get a fractional step.
 */
function scale(max: number, integer: boolean): { top: number; ticks: number[] } {
  if (max <= 0) return { top: 1, ticks: [0] };

  const raw = max / TARGET_GRIDLINES;
  const magnitude = 10 ** Math.floor(Math.log10(raw));
  const normalised = raw / magnitude;
  let step = (normalised <= 1 ? 1 : normalised <= 2 ? 2 : normalised <= 5 ? 5 : 10) * magnitude;
  if (integer) step = Math.max(1, Math.round(step));

  const top = Math.ceil(max / step) * step;
  const ticks: number[] = [];
  for (let tick = 0; tick <= top + step / 2; tick += step) ticks.push(tick);
  return { top, ticks };
}

/**
 * A single-series column chart in plain HTML.
 *
 * One series, so no legend box: the card's title says what is plotted. The
 * marks follow the house chart rules -- columns at most 24px wide with a 4px
 * rounded top and a square foot on one baseline, a 2px gap between
 * neighbours, hairline gridlines -- and the colour is `primary`, which the
 * theme already steps separately for light and dark.
 *
 * Every column is its own hover target, the full height of the plot rather
 * than just its painted bar, so a day with a tiny value is as easy to point at
 * as the best day. The keyboard gets the same readout: focus the chart and
 * walk it with the arrow keys. Nothing is only in the tooltip -- the table
 * underneath has every value.
 */
export function ColumnChart({
  columns,
  formatTick,
  integer = false,
  label,
  emptyNote,
}: {
  columns: Column[];
  formatTick: (value: number) => string;
  integer?: boolean;
  /** What the chart shows, for screen readers. */
  label: string;
  /** Shown over the plot when every value is zero. */
  emptyNote: string;
}) {
  const [active, setActive] = useState<number | null>(null);
  const tableId = useId();

  const max = Math.max(0, ...columns.map((column) => column.value));
  const { top, ticks } = scale(max, integer);
  const count = columns.length;

  // Label every n-th column, counted back from the last one: the most recent
  // bucket is the one a reader looks for first, so it is always labelled.
  const every = Math.max(1, Math.ceil(count / MAX_TICKS));
  const labelled = (index: number) => (count - 1 - index) % every === 0;

  const current = active === null ? null : columns[active];

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (count === 0) return;
    const moves: Record<string, number> = {
      ArrowRight: 1,
      ArrowLeft: -1,
      Home: -count,
      End: count,
    };
    if (!(event.key in moves)) return;
    event.preventDefault();
    const from = active ?? (moves[event.key] > 0 ? -1 : count);
    setActive(Math.min(count - 1, Math.max(0, from + moves[event.key])));
  }

  return (
    <div>
      <div className="flex gap-2">
        {/* Y axis: values right-aligned against the plot. */}
        <div className="relative h-48 w-14 shrink-0 text-right text-xs text-muted-foreground tabular-nums">
          {ticks.map((tick) => (
            <span
              key={tick}
              className="absolute right-0 translate-y-1/2 leading-none"
              style={{ bottom: `${(tick / top) * 100}%` }}
            >
              {formatTick(tick)}
            </span>
          ))}
        </div>

        <div className="min-w-0 flex-1">
          <div
            role="group"
            aria-label={`${label}. Dùng phím mũi tên để xem từng cột.`}
            aria-describedby={tableId}
            tabIndex={0}
            onKeyDown={onKeyDown}
            onBlur={() => setActive(null)}
            onPointerLeave={() => setActive(null)}
            className="relative h-48 rounded-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
          >
            {ticks.map((tick) => (
              <div
                key={tick}
                aria-hidden
                className="absolute inset-x-0 border-t border-border"
                style={{ bottom: `${(tick / top) * 100}%` }}
              />
            ))}

            <div className="absolute inset-0 flex items-end gap-[2px]">
              {columns.map((column, index) => (
                <div
                  key={column.key}
                  aria-hidden
                  onPointerEnter={() => setActive(index)}
                  className="flex h-full min-w-0 flex-1 items-end justify-center"
                >
                  <div
                    className={cn(
                      "w-full max-w-6 rounded-t-[4px] bg-primary transition-opacity",
                      active !== null && active !== index && "opacity-40",
                    )}
                    style={{
                      height: `${(column.value / top) * 100}%`,
                      // A value too small to see at this scale still shows as
                      // a sliver: "a little" and "nothing" must not look alike.
                      minHeight: column.value > 0 ? 2 : 0,
                    }}
                  />
                </div>
              ))}
            </div>

            {max === 0 ? (
              <p className="absolute inset-0 flex items-center justify-center px-4 text-center text-sm text-muted-foreground">
                {emptyNote}
              </p>
            ) : null}

            {current && active !== null ? (
              <div
                role="status"
                className={cn(
                  "pointer-events-none absolute top-0 z-10 min-w-32 rounded-md border bg-popover px-3 py-2 text-popover-foreground shadow-md",
                  // Beside the column, never over it -- the tallest column
                  // is the one most likely to be pointed at -- and on the
                  // side with room, so it stays inside the plot.
                  active < count / 2 ? "ml-4" : "-ml-4 -translate-x-full",
                )}
                style={{ left: `${((active + 0.5) / count) * 100}%` }}
              >
                <p className="font-semibold tabular-nums">{current.display}</p>
                <p className="text-xs text-muted-foreground">{current.label}</p>
                {current.detail ? (
                  <p className="text-xs text-muted-foreground">{current.detail}</p>
                ) : null}
              </div>
            ) : null}
          </div>

          <div aria-hidden className="relative mt-2 h-4 text-xs text-muted-foreground">
            {columns.map((column, index) =>
              labelled(index) ? (
                <span
                  key={column.key}
                  className="absolute -translate-x-1/2 whitespace-nowrap leading-none"
                  style={{ left: `${((index + 0.5) / count) * 100}%` }}
                >
                  {column.tick}
                </span>
              ) : null,
            )}
          </div>
        </div>
      </div>

      <details className="mt-3 text-sm">
        <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
          Xem dạng bảng
        </summary>
        <div className="mt-2 max-h-64 overflow-y-auto rounded-md border">
          <table id={tableId} className="w-full text-sm">
            <caption className="sr-only">{label}</caption>
            <tbody>
              {columns.map((column) => (
                <tr key={column.key} className="border-b last:border-0">
                  <th scope="row" className="px-3 py-1.5 text-left font-normal text-muted-foreground">
                    {column.label}
                  </th>
                  <td className="px-3 py-1.5 text-right tabular-nums">{column.display}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
