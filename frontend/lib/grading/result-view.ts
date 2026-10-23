/**
 * What the result panel says about a run, worked out away from React.
 *
 * The panel draws one list of cases for every moment of a run — queued,
 * grading, finished — so the rows here have one shape whichever source they
 * came from: the live channel (`caseSlots`, letters and durations only), or the
 * finished submission from the REST endpoint (which alone may carry a sample's
 * output). Hidden cases never get input, expectation or output here; the
 * server does not send them, and nothing below invents them.
 */

import type { SubmissionResult, TestCaseSample } from "@/lib/api/submissions";

// Types only: `npm test` runs this file under plain Node, which resolves no
// extensionless import.
import type { CaseSlot } from "./run-progress";
import type { Verdict } from "./verdicts";

export interface CaseRow extends CaseSlot {
  /** A sample's input, once the run is over; null for hidden cases. */
  input: string | null;
  /** A sample's expected output; null for hidden cases. */
  expected: string | null;
  /** What the program printed on a sample (truncated by the server); null otherwise. */
  stdout: string | null;
}

/** The live list, as rows: nothing to open until the run is over. */
export function liveRows(slots: readonly CaseSlot[]): CaseRow[] {
  return slots.map((slot) => ({ ...slot, input: null, expected: null, stdout: null }));
}

/**
 * A run that is queued has not said how many cases it will judge, but the page
 * knows the list it will be judged against: the samples for a trial, every
 * case for a submission. Drawn as waiting rows so the panel keeps its height
 * when the first event arrives.
 */
export function queuedRows(cases: readonly TestCaseSample[], trial: boolean): CaseRow[] {
  return [...cases]
    .filter((row) => !trial || !row.is_hidden)
    .sort((a, b) => a.position - b.position)
    .map((row) => ({
      label: row.position + 1,
      isHidden: row.is_hidden,
      verdict: null,
      runTimeMs: null,
      state: "pending" as const,
      input: null,
      expected: null,
      stdout: null,
    }));
}

/** The finished run, case by case, with a sample's input and output beside it. */
export function finishedRows(
  results: readonly SubmissionResult[],
  cases: readonly TestCaseSample[],
): CaseRow[] {
  const byPosition = new Map(cases.map((row) => [row.position, row]));
  return [...results]
    .sort((a, b) => a.position - b.position)
    .map((result) => {
      const sample = result.is_hidden ? undefined : byPosition.get(result.position);
      return {
        label: result.position + 1,
        isHidden: result.is_hidden,
        verdict: result.verdict,
        runTimeMs: result.run_time_ms,
        state: "done" as const,
        input: sample?.sample_input ?? null,
        expected: sample?.sample_output ?? null,
        stdout: result.is_hidden ? null : result.stdout_trunc,
      };
    });
}

export interface RunSummary {
  total: number;
  passed: number;
  /** The slowest case, which is what the submission's own `run_time_ms` is too. */
  slowestMs: number | null;
  /** The first case that did not pass — the one Naomi points at. */
  firstFailing: CaseRow | null;
}

export function summarize(rows: readonly CaseRow[]): RunSummary {
  let passed = 0;
  let slowestMs: number | null = null;
  let firstFailing: CaseRow | null = null;
  for (const row of rows) {
    if (row.state !== "done" || row.verdict === null) continue;
    if (row.verdict === "AC") passed += 1;
    else firstFailing ??= row;
    if (row.runTimeMs !== null) slowestMs = Math.max(slowestMs ?? 0, row.runTimeMs);
  }
  return { total: rows.length, passed, slowestMs, firstFailing };
}

const LEAD: Record<Verdict, string> = {
  AC: "Đúng ở",
  WA: "Sai đầu tiên ở",
  TLE: "Quá giờ ở",
  MLE: "Vượt bộ nhớ ở",
  RE: "Dừng giữa chừng ở",
  CE: "Lỗi cú pháp ở",
  SE: "Lỗi hệ thống ở",
};

/** One line under the verdict saying where it went wrong, and what can be seen of it. */
export function firstProblem(row: CaseRow): string {
  const lead = LEAD[row.verdict as Verdict] ?? LEAD.SE;
  const where = row.isHidden
    ? "test ẩn, chỉ biết đúng hay sai."
    : "test mẫu, xem đầu ra ở bên dưới.";
  return `${lead} test #${row.label} — ${where}`;
}

/** Short enough to say on the row itself, without opening it. */
const SHORT = 24;

/**
 * "in ra 2, mong đợi 3" for a wrong sample whose answer fits on one line;
 * null when it does not, and the reader has to open the row to compare.
 */
export function shortMismatch(row: CaseRow): string | null {
  if (row.verdict !== "WA" || row.isHidden || row.stdout === null || row.expected === null) {
    return null;
  }
  const got = row.stdout.replace(/\s+$/, "");
  const expected = row.expected.replace(/\s+$/, "");
  if (got.includes("\n") || expected.includes("\n")) return null;
  if (got.length > SHORT || expected.length > SHORT) return null;
  return got === "" ? `không in gì, mong đợi ${expected}` : `in ra ${got}, mong đợi ${expected}`;
}

const SECONDS = new Intl.NumberFormat("vi-VN", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});
const LIMIT = new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 2 });

/** A measured duration: "0,37 s". */
export function formatSeconds(ms: number): string {
  return `${SECONDS.format(ms / 1000)} s`;
}

/** A limit in words: "2 giây", "1,5 giây". */
export function formatLimit(ms: number): string {
  return `${LIMIT.format(ms / 1000)} giây`;
}

/** What the language is called on the exercise card. */
export function languageLabel(language: string): string {
  return language === "python" ? "Python 3" : language;
}
