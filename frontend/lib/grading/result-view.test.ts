// node --test lib/grading/result-view.test.ts  (npm test runs every *.test.ts)
//
// The numbers are the demo database's own: exercise "đếm số chẵn" (2 samples,
// 4 hidden cases) and the WA submission of 18/10/2026 that forgot 0 and the
// negative numbers.
import assert from "node:assert/strict";
import { test } from "node:test";

import type { SubmissionResult, TestCaseSample } from "../api/submissions.ts";
import { formatDateTime } from "../format.ts";
import {
  finishedRows,
  firstProblem,
  formatLimit,
  formatSeconds,
  liveRows,
  queuedRows,
  shortMismatch,
  summarize,
} from "./result-view.ts";

const cases: TestCaseSample[] = [
  { id: "c0", position: 0, is_hidden: false, sample_input: "5\n1 2 3 4 6\n", sample_output: "3\n", score_weight: 1 },
  { id: "c1", position: 1, is_hidden: false, sample_input: "3\n1 3 5\n", sample_output: "0\n", score_weight: 1 },
  { id: "c2", position: 2, is_hidden: true, sample_input: null, sample_output: null, score_weight: 1 },
  { id: "c3", position: 3, is_hidden: true, sample_input: null, sample_output: null, score_weight: 1 },
  { id: "c4", position: 4, is_hidden: true, sample_input: null, sample_output: null, score_weight: 2 },
  { id: "c5", position: 5, is_hidden: true, sample_input: null, sample_output: null, score_weight: 2 },
];

const result = (position: number, verdict: string, ms: number, stdout: string | null): SubmissionResult => ({
  test_case_id: `c${position}`,
  position,
  is_hidden: position >= 2,
  verdict,
  run_time_ms: ms,
  stdout_trunc: stdout,
});

// Shuffled on purpose: rows follow the run's order, not the response's.
const waRun = [
  result(4, "WA", 418, null),
  result(0, "AC", 416, "3\n"),
  result(1, "AC", 366, "0\n"),
  result(2, "AC", 316, null),
  result(5, "WA", 316, null),
  result(3, "AC", 366, null),
];

test("finished rows run in order and carry a sample's input and output, never a hidden one's", () => {
  const rows = finishedRows(waRun, cases);
  assert.deepEqual(rows.map((r) => r.label), [1, 2, 3, 4, 5, 6]);
  assert.deepEqual(rows[0], {
    label: 1,
    isHidden: false,
    verdict: "AC",
    runTimeMs: 416,
    state: "done",
    input: "5\n1 2 3 4 6\n",
    expected: "3\n",
    stdout: "3\n",
  });
  for (const row of rows.slice(2)) {
    assert.equal(row.input, null);
    assert.equal(row.expected, null);
    assert.equal(row.stdout, null);
  }
});

test("a hidden result never shows output, even if one reached the client", () => {
  const leaked = [{ ...result(3, "WA", 300, "secret\n") }];
  assert.equal(finishedRows(leaked, cases)[0].stdout, null);
});

test("the summary of the real WA run: 4 of 6, slowest 0,42 s, first wrong is hidden #5", () => {
  const summary = summarize(finishedRows(waRun, cases));
  assert.equal(summary.total, 6);
  assert.equal(summary.passed, 4);
  assert.equal(summary.slowestMs, 418);
  assert.equal(summary.firstFailing?.label, 5);
  assert.equal(
    firstProblem(summary.firstFailing!),
    "Sai đầu tiên ở test #5 — test ẩn, chỉ biết đúng hay sai.",
  );
});

test("rows still waiting or running count for nothing", () => {
  const rows = liveRows([
    { label: 1, isHidden: false, verdict: "AC", runTimeMs: 367, state: "done" },
    { label: 2, isHidden: false, verdict: null, runTimeMs: null, state: "running" },
    { label: 3, isHidden: true, verdict: null, runTimeMs: null, state: "pending" },
  ]);
  assert.deepEqual(summarize(rows), { total: 3, passed: 1, slowestMs: 367, firstFailing: null });
});

test("a wrong sample points at the output below, with the words of its letter", () => {
  const rows = finishedRows([result(0, "TLE", 2000, ""), result(1, "AC", 300, "0\n")], cases);
  assert.equal(firstProblem(rows[0]), "Quá giờ ở test #1 — test mẫu, xem đầu ra ở bên dưới.");
  const unknown = { ...rows[0], verdict: "XYZ" };
  assert.match(firstProblem(unknown), /^Lỗi hệ thống ở test #1/);
});

test("a short wrong answer is said on the row; a long or multi-line one is not", () => {
  const [wrong] = finishedRows([result(0, "WA", 352, "2\n")], cases);
  assert.equal(shortMismatch(wrong), "in ra 2, mong đợi 3");
  assert.equal(shortMismatch({ ...wrong, stdout: "" }), "không in gì, mong đợi 3");
  assert.equal(shortMismatch({ ...wrong, stdout: "1\n2\n" }), null);
  assert.equal(shortMismatch({ ...wrong, stdout: "x".repeat(25) }), null);
  assert.equal(shortMismatch({ ...wrong, verdict: "AC" }), null);
  assert.equal(shortMismatch({ ...wrong, isHidden: true }), null);
});

test("a queued run waits on the samples for a trial and on every case for a submission", () => {
  assert.deepEqual(queuedRows(cases, true).map((r) => r.label), [1, 2]);
  const all = queuedRows(cases, false);
  assert.deepEqual(all.map((r) => r.label), [1, 2, 3, 4, 5, 6]);
  assert.ok(all.every((r) => r.state === "pending" && r.verdict === null));
});

test("durations and limits read the Vietnamese way", () => {
  assert.equal(formatSeconds(367), "0,37 s");
  assert.equal(formatSeconds(2000), "2,00 s");
  assert.equal(formatLimit(2000), "2 giây");
  assert.equal(formatLimit(1500), "1,5 giây");
  assert.equal(formatLimit(500), "0,5 giây");
});

test("a submission time is Vietnamese time, whatever the machine's zone", () => {
  assert.equal(formatDateTime("2026-10-18T14:21:37.724Z"), "21:21 · 18/10/2026");
  assert.equal(formatDateTime("2026-10-18T17:05:00Z"), "00:05 · 19/10/2026");
});
