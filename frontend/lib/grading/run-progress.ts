/**
 * Turning a stream of grading events into a row per test case.
 *
 * The channel says three different things depending on how the client is
 * connected, and this module is where the three are reconciled into one
 * picture the page can draw:
 *
 * * a **progress** event names one case that just finished — its letter, how
 *   long it took, and whether it is hidden;
 * * a **snapshot** names no case at all, only how many are done. Polling only
 *   ever produces these, and so does a socket that has been quiet;
 * * before either arrives there is nothing but the case list the page already
 *   loaded to show the samples.
 *
 * So a row is drawn from whichever of those knows the most about it, and a
 * row whose verdict nobody has told us stays a row — grey, numbered, waiting.
 *
 * What that buys on the polling path is honesty, not motion. Measured against
 * the running stack: a snapshot's `completed_cases` counts `submission_results`
 * rows, and the worker writes all of them in one commit when the run is over,
 * so a polled list sits at "đang chấm test 1/8" and then jumps straight to the
 * finished result. The live channel is what makes the list move; this module
 * makes sure the page never invents movement it was not told about.
 *
 * Nothing here can leak a hidden case's input or output for the simple reason
 * that no input or output reaches it. A `GradingCaseEvent` carries a letter
 * and a duration; the answer key lives behind `GET /submissions/{id}`, which
 * strips it. See `sandbox-grading`, rule 9.
 */

import type {
  GradingCaseEvent,
  GradingEvent,
  TestCaseSample,
} from "@/lib/api/submissions";

/** What the grader has told us about each case, in the order it ran them. */
export type CaseReports = readonly (GradingCaseEvent | null)[];

export type CaseState = "pending" | "running" | "done";

/** One line of the live list. */
export interface CaseSlot {
  /** What to call it on screen — the case's position + 1, counting from 1. */
  label: number;
  /** Null while nobody has said; a row is never assumed to be visible. */
  isHidden: boolean | null;
  /** Only ever set on a finished row, and only if a progress event arrived. */
  verdict: string | null;
  runTimeMs: number | null;
  state: CaseState;
}

/**
 * Fold one event into what we already know, keyed by the run's own ordering.
 *
 * The worker sends `completed_cases = index + 1` alongside each case, so the
 * event carries its own slot number and this never has to guess or dedupe: a
 * message delivered twice lands in the same slot and changes nothing.
 *
 * Everything after that slot is dropped. In the ordinary run there is nothing
 * after it; there is only when a job was retried and the grading started over,
 * and in that case the old run's later verdicts are stale — showing them
 * beneath a case that is being re-judged would be a page telling a story that
 * already stopped being true.
 */
export function mergeCaseReport(
  known: CaseReports,
  event: GradingEvent,
): CaseReports {
  if (event.case === null) return known;

  const index = Math.max(event.completed_cases - 1, 0);
  const next: (GradingCaseEvent | null)[] = [];
  for (let i = 0; i < index; i += 1) next.push(known[i] ?? null);
  next.push(event.case);
  return next;
}

/**
 * The cases this run will judge, in the order it will judge them — if we can
 * say so without guessing.
 *
 * A submission is judged against every case; a trial run only against the
 * samples. Rather than plumb the trial flag down here, the count decides:
 * whichever of the two lists is as long as the run says it is, is the list.
 * When neither matches — an instructor edited the exercise mid-run, say — the
 * answer is null and rows fall back to counting from one, which is honest
 * about knowing less rather than confidently numbering them wrong.
 */
export function predictRun(
  cases: readonly TestCaseSample[],
  total: number,
): readonly TestCaseSample[] | null {
  const ordered = [...cases].sort((a, b) => a.position - b.position);
  if (ordered.length === total) return ordered;

  const samples = ordered.filter((row) => !row.is_hidden);
  if (samples.length === total) return samples;

  return null;
}

/**
 * The list to draw right now.
 *
 * The state of a row is decided by the count, not by what arrived: case `i` is
 * done when `i < completed_cases`, and the one at the boundary is the one
 * being judged. That is what makes "đang chấm test 3/10" a claim about the
 * grader rather than about the network — a student on polling sees the same
 * row move even though no per-case message ever reached them.
 *
 * A submission still queued has no case running yet, however many are waiting.
 */
export function caseSlots(
  event: GradingEvent | null,
  known: CaseReports,
  cases: readonly TestCaseSample[],
): CaseSlot[] {
  const total = event?.total_cases ?? 0;
  if (event === null || total <= 0) return [];

  const predicted = predictRun(cases, total);
  const done = event.status === "pending" ? -1 : event.completed_cases;

  return Array.from({ length: total }, (_, index): CaseSlot => {
    const reported = known[index] ?? null;
    const guessed = predicted?.[index] ?? null;
    const finished = index < done;

    return {
      label: (reported?.position ?? guessed?.position ?? index) + 1,
      isHidden: reported?.is_hidden ?? guessed?.is_hidden ?? null,
      verdict: finished ? (reported?.verdict ?? null) : null,
      runTimeMs: finished ? (reported?.run_time_ms ?? null) : null,
      state: finished ? "done" : index === done ? "running" : "pending",
    };
  });
}
