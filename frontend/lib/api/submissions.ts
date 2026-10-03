/**
 * A student's own submissions: reading one, and watching one being graded.
 *
 * Deliberately not in `grading.ts`. That file is the instructor's side and its
 * `TestCase` carries an answer key; a page that submits code must never import
 * a type whose `expected_output` is always present, because that type is an
 * assumption, and the assumption is wrong for every hidden case.
 */

import { apiFetch, apiUrl, ApiError } from "./client";

/**
 * A test case as a student may see it.
 *
 * The counterpart of `TestCase` in `grading.ts`, and the difference is the
 * whole point: there is no `expected_output` here. A hidden case arrives with
 * both sample fields null, so code that renders one cannot accidentally print
 * an answer key — there is no field holding one.
 */
export interface TestCaseSample {
  id: string;
  position: number;
  is_hidden: boolean;
  sample_input: string | null;
  sample_output: string | null;
  score_weight: number;
}

/**
 * The exercise's cases, in the detail this caller is entitled to.
 *
 * The same URL answers the instructor with the answer key. A student gets
 * this shape, which is decided by the server per caller — the type here is a
 * description of what arrives, not a request for it.
 */
export function listSampleTestCases(
  accessToken: string,
  exerciseId: string,
): Promise<TestCaseSample[]> {
  return apiFetch<TestCaseSample[]>(
    `/api/v1/code-exercises/${exerciseId}/test-cases`,
    { accessToken },
  );
}

export interface SubmissionResult {
  test_case_id: string;
  position: number;
  is_hidden: boolean;
  verdict: string;
  run_time_ms: number | null;
  /** Null for every hidden case, and for those the server never stored it. */
  stdout_trunc: string | null;
}

export interface Submission {
  id: string;
  exercise_id: string;
  user_id: string;
  language: string;
  /** True for a "chạy thử" run: sample cases only, and not part of history. */
  is_trial: boolean;
  status: SubmissionStatus;
  verdict: string | null;
  score: number | null;
  run_time_ms: number | null;
  message: string | null;
  created_at: string;
}

export interface SubmissionDetail extends Submission {
  code: string;
  /** How many cases this will be judged against — known before any has run. */
  total_cases: number;
  results: SubmissionResult[];
}

export type SubmissionStatus = "pending" | "running" | "done" | "error";

/** Statuses with nothing left to wait for. */
const TERMINAL: readonly string[] = ["done", "error"];

export function isFinished(status: string): boolean {
  return TERMINAL.includes(status);
}

export function getSubmission(
  submissionId: string,
  accessToken: string | null,
): Promise<SubmissionDetail> {
  return apiFetch<SubmissionDetail>(`/api/v1/submissions/${submissionId}`, {
    accessToken,
  });
}

/** Hand the code in. Counts, and appears in the history. */
export function createSubmission(
  accessToken: string,
  exerciseId: string,
  code: string,
): Promise<Submission> {
  return apiFetch<Submission>(
    `/api/v1/code-exercises/${exerciseId}/submissions`,
    { method: "POST", accessToken, body: JSON.stringify({ code }) },
  );
}

/**
 * Run the code against the sample cases only. Does not count.
 *
 * A different endpoint rather than a flag, because the two do different things
 * to a student's record — and a boolean in a body is the kind of thing a
 * client gets wrong silently, in the direction of turning every rehearsal into
 * a submission.
 */
export function createTrialRun(
  accessToken: string,
  exerciseId: string,
  code: string,
): Promise<Submission> {
  return apiFetch<Submission>(
    `/api/v1/code-exercises/${exerciseId}/trial-runs`,
    { method: "POST", accessToken, body: JSON.stringify({ code }) },
  );
}

export interface SubmissionPage {
  items: Submission[];
  total: number;
  page: number;
  page_size: number;
}

/** Your own attempts at this exercise, newest first. Trial runs are not here. */
export function listSubmissions(
  accessToken: string,
  exerciseId: string,
  pageSize = 20,
): Promise<SubmissionPage> {
  return apiFetch<SubmissionPage>(
    `/api/v1/code-exercises/${exerciseId}/submissions?page=1&page_size=${pageSize}`,
    { accessToken },
  );
}

/* -- Watching one being graded -------------------------------------------- */

export interface GradingCaseEvent {
  position: number;
  is_hidden: boolean;
  verdict: string;
  run_time_ms: number | null;
}

/**
 * One update about a submission being graded, from either transport.
 *
 * `snapshot` was read from the database, `progress` was published by the
 * worker mid-run. A caller that does not care which can ignore `type` — both
 * are complete descriptions of where the submission stands, which is what
 * lets the fallback below be a real fallback rather than a different feature.
 */
export interface GradingEvent {
  type: "snapshot" | "progress";
  submission_id: string;
  status: SubmissionStatus;
  total_cases: number;
  completed_cases: number;
  case: GradingCaseEvent | null;
  verdict: string | null;
  score: number | null;
}

/** Matches `WS_NOT_FOUND` in the API: there is nothing here to watch. */
const WS_NOT_FOUND = 4404;
/** The subprotocol the token rides in — never a query string. */
const BEARER = "bearer";
const POLL_INTERVAL_MS = 2000;

export interface WatchOptions {
  submissionId: string;
  accessToken: string | null;
  onEvent: (event: GradingEvent) => void;
}

function eventFromDetail(detail: SubmissionDetail): GradingEvent {
  return {
    type: "snapshot",
    submission_id: detail.id,
    status: detail.status,
    total_cases: detail.total_cases,
    // The results that exist are the cases that finished. Same rule as the
    // server's snapshot, so the two paths cannot disagree about the count.
    completed_cases: detail.results.length,
    case: null,
    verdict: detail.verdict,
    score: detail.score,
  };
}

function websocketUrl(path: string): string {
  // apiUrl may return a root-relative path (same-origin deployments), which a
  // WebSocket constructor will not take. Resolving against the page gives an
  // absolute URL either way.
  const url = new URL(apiUrl(path), window.location.href);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.toString();
}

/**
 * Watch one submission until it is graded. Returns a function that stops.
 *
 * Tries the WebSocket; falls back to polling if it cannot be opened, if it
 * closes before the grading finished, or if the browser refuses it outright.
 * The fallback is not a degraded mode to apologise for — polling is what the
 * socket is an optimisation over, and the one case where it is *not* used is
 * a 4404, because asking again cannot make a submission exist.
 *
 * Both paths deliver the same `GradingEvent`, so a caller renders one thing
 * and never learns which transport it came from.
 */
export function watchSubmission({
  submissionId,
  accessToken,
  onEvent,
}: WatchOptions): () => void {
  let stopped = false;
  let socket: WebSocket | null = null;
  let timer: ReturnType<typeof setTimeout> | null = null;

  const stop = () => {
    stopped = true;
    if (timer !== null) clearTimeout(timer);
    // Detach first: closing a socket fires `onclose`, which would otherwise
    // start the very poll this call is trying to end.
    if (socket !== null) {
      socket.onclose = null;
      socket.onmessage = null;
      socket.onerror = null;
      socket.close();
    }
  };

  const deliver = (event: GradingEvent) => {
    if (stopped) return;
    onEvent(event);
    if (isFinished(event.status)) stop();
  };

  const poll = async () => {
    if (stopped) return;
    try {
      deliver(eventFromDetail(await getSubmission(submissionId, accessToken)));
    } catch (error) {
      // A submission that is gone, or a session that is over, will not come
      // back by asking again. Anything else — a blip, a restarting API — will.
      if (error instanceof ApiError && (error.status === 404 || error.status === 401)) {
        stop();
      }
    }
    if (!stopped) timer = setTimeout(poll, POLL_INTERVAL_MS);
  };

  if (accessToken === null) {
    void poll();
    return stop;
  }

  try {
    socket = new WebSocket(websocketUrl(`/api/v1/submissions/${submissionId}/events`), [
      BEARER,
      accessToken,
    ]);
  } catch {
    void poll();
    return stop;
  }

  socket.onmessage = (message) => {
    try {
      deliver(JSON.parse(message.data) as GradingEvent);
    } catch {
      // Unreadable frame: ignoring it leaves the socket alive, and the
      // server's next snapshot repairs whatever this one was going to say.
    }
  };

  socket.onclose = (event) => {
    if (stopped) return;
    if (event.code === WS_NOT_FOUND) {
      stop();
      return;
    }
    void poll();
  };

  return stop;
}
