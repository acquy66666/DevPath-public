"use client";

import { Check, Circle, Loader2, X } from "lucide-react";

import type { CaseSlot } from "@/lib/grading/run-progress";
import { TONE_BADGE, verdictLabel, verdictTone } from "@/lib/grading/verdicts";

/**
 * The test cases of a run in flight, one line each, filling in as they land.
 *
 * A progress bar says how far; this says what happened. The difference matters
 * to someone waiting on ten cases: seeing test 4 come back red is the moment
 * they learn their answer is wrong, and it arrives seconds before the verdict
 * does.
 *
 * There is no output on these rows and no input — not because a hidden case
 * would leak (the events carry neither), but because a row that shows output
 * for samples and nothing for hidden cases invites the reader to compare the
 * gaps. Output belongs to the finished result below, which is fetched from the
 * endpoint that knows the rule.
 */
export function LiveCases({ slots }: { slots: CaseSlot[] }) {
  if (slots.length === 0) return null;

  return (
    <ul className="mt-3 grid gap-1.5 sm:grid-cols-2">
      {slots.map((slot) => (
        <li
          key={slot.label}
          className={`flex items-center gap-2 rounded-md border px-2.5 py-1.5 text-xs transition-colors ${
            slot.state === "pending"
              ? "border-dashed text-muted-foreground"
              : "bg-background"
          }`}
        >
          <Mark slot={slot} />
          <span className="font-medium">Test {slot.label}</span>
          {slot.isHidden ? (
            <span className="rounded bg-muted px-1 py-0.5 text-[11px] text-muted-foreground">
              Ẩn
            </span>
          ) : null}
          <span className="ml-auto flex items-center gap-2">
            {slot.runTimeMs != null ? (
              <span className="text-muted-foreground">{slot.runTimeMs} ms</span>
            ) : null}
            <Status slot={slot} />
          </span>
        </li>
      ))}
    </ul>
  );
}

/** The icon: what this case is doing, before any reading happens. */
function Mark({ slot }: { slot: CaseSlot }) {
  if (slot.state === "running") {
    return <Loader2 className="size-3.5 shrink-0 animate-spin text-primary" aria-hidden />;
  }
  if (slot.state === "pending" || slot.verdict === null) {
    return <Circle className="size-3.5 shrink-0 opacity-50" aria-hidden />;
  }
  return verdictTone(slot.verdict) === "pass" ? (
    <Check className="size-3.5 shrink-0 text-emerald-600 dark:text-emerald-400" aria-hidden />
  ) : (
    <X className="size-3.5 shrink-0 text-rose-600 dark:text-rose-400" aria-hidden />
  );
}

/**
 * The words on the right. A case the count says is finished but no event
 * described says exactly that and no more — it does not borrow a verdict it
 * was never told. Rare in practice: today the only source of a count without
 * letters is a snapshot, and the database learns every case at once when the
 * run ends. It is here because "done, and I do not know how" is a state this
 * page can be in, and the alternative is a row that lies in one direction or
 * the other.
 */
function Status({ slot }: { slot: CaseSlot }) {
  if (slot.state === "running") {
    return <span className="font-medium text-primary">Đang chấm…</span>;
  }
  if (slot.state === "pending") return <span>Chờ</span>;
  if (slot.verdict === null) {
    return <span className="text-muted-foreground">Đã chấm</span>;
  }

  return (
    <span
      className={`rounded px-1.5 py-0.5 font-semibold ${TONE_BADGE[verdictTone(slot.verdict)]}`}
    >
      {verdictLabel(slot.verdict)}
    </span>
  );
}
