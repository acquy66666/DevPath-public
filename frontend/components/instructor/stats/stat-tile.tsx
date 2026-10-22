import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";

import { cn } from "@/lib/utils";

import { change, formatRate } from "./format";

/**
 * One headline figure: a label, the value, and how it moved.
 *
 * The movement carries an arrow and words as well as a colour -- green-up /
 * red-down on its own says nothing to a reader who cannot tell the two apart.
 * From a previous period of zero there is no honest percentage, so the tile
 * says what the previous figure was instead of printing "+∞ %".
 */
export function StatTile({
  label,
  value,
  current,
  previous,
  previousLabel,
  previousDisplay,
  note,
}: {
  label: string;
  value: string;
  /** Raw numbers for the comparison; leave out for a figure with no period. */
  current?: number;
  previous?: number;
  /** "30 ngày trước đó". */
  previousLabel?: string;
  /** The previous figure, formatted like `value`. */
  previousDisplay?: string;
  note?: string;
}) {
  const compared = current !== undefined && previous !== undefined;
  const delta = compared ? change(current, previous) : null;

  return (
    <div className="rounded-lg border bg-card p-4">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="mt-1 text-2xl font-semibold tracking-tight">{value}</p>

      {compared ? (
        delta === null ? (
          <p className="mt-1 text-xs text-muted-foreground">
            {previousLabel}: {previousDisplay}
          </p>
        ) : (
          <p
            className={cn(
              "mt-1 flex items-center gap-1 text-xs",
              delta > 0 && "text-emerald-700 dark:text-emerald-400",
              delta < 0 && "text-red-700 dark:text-red-400",
              delta === 0 && "text-muted-foreground",
            )}
          >
            {delta > 0 ? (
              <ArrowUpRight className="size-3.5" aria-hidden />
            ) : delta < 0 ? (
              <ArrowDownRight className="size-3.5" aria-hidden />
            ) : (
              <Minus className="size-3.5" aria-hidden />
            )}
            <span>
              {delta > 0 ? "Tăng " : delta < 0 ? "Giảm " : "Không đổi "}
              {delta !== 0 ? formatRate(Math.abs(delta)) : null} so với {previousLabel}
            </span>
          </p>
        )
      ) : null}

      {note ? <p className="mt-1 text-xs text-muted-foreground">{note}</p> : null}
    </div>
  );
}
