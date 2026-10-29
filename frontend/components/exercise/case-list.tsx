"use client";

import { ChevronDown, LoaderCircle } from "lucide-react";
import { useId, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { type CaseRow, formatSeconds, shortMismatch } from "@/lib/grading/result-view";
import { VERDICT_CLASSES, asVerdict, verdictLabel } from "@/lib/grading/verdicts";
import { cn } from "@/lib/utils";

/** The colour of one case: grey while waiting, primary while judged, its letter after. */
function cellTone(row: CaseRow): string {
  if (row.state === "running") return "bg-primary/45";
  if (row.state === "pending") return "bg-border-strong";
  const letter = asVerdict(row.verdict);
  return letter ? VERDICT_CLASSES[letter].solid : "bg-muted-foreground";
}

/**
 * One segment per case, filled with the case's colour as the grader reports
 * it. While the run goes it is a progress bar (`aria-valuenow` = cases
 * judged); once it is over the same strip stays as a picture of the result,
 * and says so in words.
 */
export function CaseBar({ rows, summary }: { rows: readonly CaseRow[]; summary?: string }) {
  if (rows.length === 0) return null;
  const done = rows.filter((row) => row.state === "done").length;
  const cells = rows.map((row) => (
    <span
      key={row.label}
      className={cn("h-2 min-w-0 flex-1 rounded-full transition-colors duration-base", cellTone(row))}
    />
  ));
  return summary === undefined ? (
    <div
      role="progressbar"
      aria-label="Tiến độ chấm"
      aria-valuemin={0}
      aria-valuemax={rows.length}
      aria-valuenow={done}
      aria-valuetext={`${done}/${rows.length} test đã chấm`}
      className="flex gap-1"
    >
      {cells}
    </div>
  ) : (
    <div role="img" aria-label={summary} className="flex gap-1">
      {cells}
    </div>
  );
}

/**
 * Every case of a run, one line each: a dot in its colour, its number,
 * whether it is a sample, what it came back as, how long it took.
 *
 * Only a finished sample can be opened, to compare its output with what was
 * expected; a hidden case has nothing to show, because the server never sent
 * its input or output (sandbox-grading, rule 9). The first case that went
 * wrong is tinted and, when it is a sample, opens by itself.
 */
export function CaseList({
  rows,
  highlight = null,
  openFirst = null,
}: {
  rows: readonly CaseRow[];
  /** Label of the row to tint: the first one that went wrong. */
  highlight?: number | null;
  /** Label of the row to open on arrival. */
  openFirst?: number | null;
}) {
  const [open, setOpen] = useState<ReadonlySet<number>>(
    () => new Set(openFirst === null ? [] : [openFirst]),
  );
  const id = useId();
  if (rows.length === 0) return null;

  return (
    <ul className="divide-y divide-border overflow-hidden rounded-lg border border-border bg-card">
      {rows.map((row) => {
        const letter = asVerdict(row.verdict);
        const tone = letter ? VERDICT_CLASSES[letter] : null;
        const wrong = row.state === "done" && letter !== null && letter !== "AC";
        const openable = row.state === "done" && row.isHidden === false && row.expected !== null;
        const isOpen = openable && open.has(row.label);
        const panel = `${id}-${row.label}`;
        const mismatch = shortMismatch(row);

        return (
          <li key={row.label} className={cn(highlight === row.label && tone?.soft)}>
            <div className="flex min-h-11 items-center gap-2.5 py-1 pr-2 pl-3.5 text-body-sm">
              <span
                aria-hidden
                className={cn(
                  "size-2.5 shrink-0 rounded-xs",
                  row.state === "running" ? "bg-card ring-2 ring-primary" : cellTone(row),
                )}
              />
              <span className="w-7 shrink-0 font-mono font-semibold tabular-nums">#{row.label}</span>
              {row.isHidden === null ? null : (
                <Badge variant="muted">{row.isHidden ? "Ẩn" : "Mẫu"}</Badge>
              )}
              <span
                className={cn(
                  "min-w-0 flex-1",
                  row.state === "running" && "flex items-center gap-1.5 font-semibold text-primary",
                  (row.state === "pending" || (row.state === "done" && letter === null)) &&
                    "text-muted-foreground",
                  wrong && tone && cn("font-semibold", tone.text),
                )}
              >
                {row.state === "running" ? (
                  <>
                    <LoaderCircle className="size-3.5 motion-safe:animate-spin" aria-hidden />
                    Đang chấm…
                  </>
                ) : row.state === "pending" ? (
                  "Chờ"
                ) : letter === null ? (
                  "Đã chấm"
                ) : mismatch ? (
                  `${verdictLabel(letter)} · ${mismatch}`
                ) : (
                  verdictLabel(letter)
                )}
              </span>
              <span className="shrink-0 font-mono text-code-sm text-muted-foreground tabular-nums">
                {row.runTimeMs === null ? "—" : formatSeconds(row.runTimeMs)}
              </span>
              {openable ? (
                <Button
                  size="icon-sm"
                  variant="ghost"
                  aria-expanded={isOpen}
                  aria-controls={panel}
                  aria-label={`Xem đầu vào và đầu ra của test ${row.label}`}
                  onClick={() =>
                    setOpen((known) => {
                      const next = new Set(known);
                      if (next.has(row.label)) next.delete(row.label);
                      else next.add(row.label);
                      return next;
                    })
                  }
                >
                  <ChevronDown
                    className={cn("transition-transform duration-fast motion-reduce:transition-none", isOpen && "rotate-180")}
                    aria-hidden
                  />
                </Button>
              ) : (
                <span aria-hidden className="w-8 shrink-0" />
              )}
            </div>
            {isOpen ? (
              <div id={panel} className="grid gap-3 px-3.5 pb-3.5 sm:grid-cols-3 sm:pl-[3.25rem]">
                <Output label="Đầu vào" value={row.input ?? ""} />
                <Output label="Mong đợi" value={row.expected ?? ""} />
                <Output
                  label={
                    !wrong
                      ? "Chương trình in ra"
                      : letter === "WA"
                        ? "Chương trình in ra · khác mong đợi"
                        : "In ra trước khi bị dừng"
                  }
                  value={row.stdout ?? ""}
                  tone={wrong && tone ? tone : null}
                />
              </div>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}

function Output({
  label,
  value,
  tone = null,
}: {
  label: string;
  value: string;
  tone?: (typeof VERDICT_CLASSES)[keyof typeof VERDICT_CLASSES] | null;
}) {
  return (
    <div className="flex min-w-0 flex-col gap-1">
      <p className={cn("text-caption", tone ? cn("font-semibold", tone.text) : "text-muted-foreground")}>
        {label}
      </p>
      <pre
        className={cn(
          "max-h-40 overflow-auto rounded-md border px-2.5 py-2 font-mono text-code-sm whitespace-pre-wrap break-words",
          tone ? cn(tone.border, tone.soft) : "border-border bg-muted",
        )}
      >
        {value === "" ? <span className="text-muted-foreground">(trống)</span> : value}
      </pre>
    </div>
  );
}
