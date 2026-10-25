"use client";

import { useId } from "react";

import { Button } from "@/components/ui/button";
import { formatDateTime } from "@/lib/format";
import { LEVEL_CLASSES, type History } from "@/lib/quiz/result-view";
import { cn } from "@/lib/utils";

/**
 * "Lượt đã làm": every finished attempt, its score in the colour of its level,
 * and a way to open its marked paper again. The attempt on screen says
 * "Đang xem" instead of offering itself.
 */
export function AttemptHistory({
  history,
  viewing,
  opening,
  onOpen,
}: {
  history: History;
  /** The attempt shown above, if any. */
  viewing: string | null;
  /** The attempt being fetched, while it is. */
  opening: string | null;
  onOpen: (attemptId: string) => void;
}) {
  const titleId = useId();
  if (history.rows.length === 0) return null;

  return (
    <section aria-labelledby={titleId} className="overflow-hidden rounded-lg border bg-card">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 px-4 py-3.5">
        <h2 id={titleId} className="text-title">
          Lượt đã làm
        </h2>
        <p className="text-caption text-muted-foreground tabular-nums">
          {history.count} lượt{history.best === null ? "" : ` · cao nhất ${history.best}%`}
        </p>
      </div>
      <ul>
        {history.rows.map((row) => {
          const tone = LEVEL_CLASSES[row.level];
          const shown = row.id === viewing;
          return (
            <li
              key={row.id}
              className={cn(
                "flex min-h-12 flex-wrap items-center gap-x-4 gap-y-1 border-t border-muted py-1.5 pr-2 pl-4",
                shown && "bg-background",
              )}
            >
              <span className="w-14 text-body-sm font-semibold">Lượt {row.number}</span>
              <span
                className={cn(
                  "inline-flex h-6.5 min-w-13 items-center justify-center rounded-full px-2 text-body-sm font-semibold tabular-nums",
                  tone.soft,
                  tone.text,
                )}
              >
                {row.score}%
              </span>
              <span
                className={cn(
                  "text-body-sm",
                  row.passed ? "font-medium text-success-text" : "text-muted-foreground",
                )}
              >
                {row.passed ? "Đạt" : "Chưa đạt"}
              </span>
              <span className="text-body-sm text-muted-foreground tabular-nums">
                {formatDateTime(row.submittedAt)}
              </span>
              {shown ? (
                <span className="ml-auto pr-2 text-caption font-semibold text-link">Đang xem</span>
              ) : (
                <Button
                  variant="ghost"
                  size="sm"
                  className="ml-auto text-link"
                  disabled={opening !== null}
                  aria-label={`Xem lại lượt ${row.number}`}
                  onClick={() => onOpen(row.id)}
                >
                  {opening === row.id ? "Đang mở…" : "Xem lại"}
                </Button>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
