"use client";

import { CheckCircle2, CircleAlert, Loader2, XCircle } from "lucide-react";

import { LiveCases } from "@/components/exercise/live-cases";
import { Alert, AlertDescription } from "@/components/ui/alert";
import type {
  GradingEvent,
  SubmissionDetail,
  TestCaseSample,
} from "@/lib/api/submissions";
import { caseSlots, type CaseReports } from "@/lib/grading/run-progress";
import {
  TONE_BADGE,
  VERDICT_HINTS,
  verdictLabel,
  verdictTone,
} from "@/lib/grading/verdicts";

/**
 * What one run did, while it does it and after it is finished.
 *
 * Two sources feed this and they are deliberately not merged into one state:
 * `event` is the live progress (or the polled snapshot — the client cannot
 * tell), and `detail` is the finished result read from the REST endpoint. The
 * first says how far along; only the second carries per-case output, because
 * the live channel has no field for output at all.
 *
 * `reports` is the accumulation of the first: one entry per case the grader
 * has finished, in run order. The two lists below — the live one and the
 * final one — are therefore the same list at two levels of detail, and the
 * handover between them happens when the run ends and `detail` arrives.
 */
export function RunResult({
  event,
  reports,
  detail,
  samples,
  trial,
}: {
  event: GradingEvent | null;
  reports: CaseReports;
  detail: SubmissionDetail | null;
  samples: TestCaseSample[];
  trial: boolean;
}) {
  // The event first: while a run is going it is fresher than a detail that
  // was fetched when the run started. A history pick has no event and falls
  // through to the row it was asked about.
  const status = event?.status ?? detail?.status ?? "pending";
  const running = status === "pending" || status === "running";

  if (running) {
    const done = event?.completed_cases ?? 0;
    const total = event?.total_cases ?? 0;
    // Which case is on the grader's bench: the one after everything finished,
    // except at the very end, where the last case is done and the verdict is
    // being written — no case is running then, and "test 11/10" would be a lie
    // told by arithmetic.
    const current = Math.min(done + 1, total);

    return (
      <div className="rounded-lg border bg-muted/30 p-4">
        <p
          className="flex items-center gap-2 text-sm font-medium"
          // Announced rather than only drawn: a student using a screen reader
          // is waiting on exactly the same thing everyone else is.
          aria-live="polite"
        >
          <Loader2 className="size-4 animate-spin" aria-hidden />
          {status === "pending"
            ? "Đang chờ tới lượt chấm…"
            : total > 0
              ? `Đang chấm test ${current}/${total}`
              : "Đang chấm…"}
        </p>
        {total > 0 ? (
          <div
            className="mt-3 h-1.5 overflow-hidden rounded-full bg-muted"
            role="progressbar"
            aria-valuenow={done}
            aria-valuemin={0}
            aria-valuemax={total}
          >
            <div
              className="h-full bg-primary transition-[width] duration-300"
              style={{ width: `${total === 0 ? 0 : (done / total) * 100}%` }}
            />
          </div>
        ) : null}
        <LiveCases slots={caseSlots(event, reports, samples)} />
      </div>
    );
  }

  // The platform failed, not the submission. The sandbox rules say this is
  // never charged to the student, and the wording is where that shows up.
  if (status === "error") {
    return (
      <Alert>
        <CircleAlert aria-hidden />
        <AlertDescription>
          {detail?.message ??
            "Hệ thống chấm bài gặp sự cố. Bài của bạn chưa được chấm — thử lại sau ít phút nhé."}
        </AlertDescription>
      </Alert>
    );
  }

  const verdict = event?.verdict ?? detail?.verdict ?? null;
  const tone = verdictTone(verdict);
  const score = event?.score ?? detail?.score ?? null;
  const byPosition = new Map(samples.map((sample) => [sample.position, sample]));

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <span
          className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-sm font-semibold ${TONE_BADGE[tone]}`}
        >
          {tone === "pass" ? (
            <CheckCircle2 className="size-4" aria-hidden />
          ) : (
            <XCircle className="size-4" aria-hidden />
          )}
          {verdictLabel(verdict)}
        </span>
        {score !== null ? (
          <span className="text-sm text-muted-foreground">
            {trial ? "Test mẫu: " : "Điểm: "}
            <strong className="text-foreground">{score}/100</strong>
          </span>
        ) : null}
        {detail?.run_time_ms != null ? (
          <span className="text-sm text-muted-foreground">
            Chậm nhất {detail.run_time_ms} ms
          </span>
        ) : null}
        {trial ? (
          <span className="rounded bg-muted px-2 py-0.5 text-xs text-muted-foreground">
            Chạy thử — không tính vào lịch sử
          </span>
        ) : null}
      </div>

      {verdict !== null && VERDICT_HINTS[verdict] ? (
        <p className="text-sm text-muted-foreground">{VERDICT_HINTS[verdict]}</p>
      ) : null}

      {/* A compile error has no per-case results: the program never became a
          program. The compiler's own words are the only thing to show. */}
      {detail?.message && status === "done" ? (
        <pre className="max-h-48 overflow-auto rounded-lg bg-muted p-3 text-xs whitespace-pre-wrap">
          {detail.message}
        </pre>
      ) : null}

      {detail && detail.results.length > 0 ? (
        <ul className="divide-y rounded-lg border">
          {detail.results.map((result) => {
            const sample = byPosition.get(result.position);
            const caseTone = verdictTone(result.verdict);

            return (
              <li key={result.test_case_id} className="space-y-2 p-3">
                <div className="flex flex-wrap items-center gap-2 text-sm">
                  <span className="font-medium">Test {result.position + 1}</span>
                  <span
                    className={`rounded px-1.5 py-0.5 text-xs font-semibold ${TONE_BADGE[caseTone]}`}
                  >
                    {verdictLabel(result.verdict)}
                  </span>
                  {result.is_hidden ? (
                    <span className="rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
                      Ẩn
                    </span>
                  ) : null}
                  {result.run_time_ms != null ? (
                    <span className="text-xs text-muted-foreground">
                      {result.run_time_ms} ms
                    </span>
                  ) : null}
                </div>

                {/* Only a sample case has anything to compare: the server
                    never stored what a hidden case printed, and the input it
                    printed it for is not ours to show either. */}
                {result.is_hidden ? null : (
                  <div className="grid gap-2 text-xs sm:grid-cols-3">
                    <Field label="Input" value={sample?.sample_input ?? ""} />
                    <Field label="Mong đợi" value={sample?.sample_output ?? ""} />
                    <Field
                      label="Chương trình in ra"
                      value={result.stdout_trunc ?? ""}
                      wrong={result.verdict !== "AC"}
                    />
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
}

function Field({
  label,
  value,
  wrong = false,
}: {
  label: string;
  value: string;
  wrong?: boolean;
}) {
  return (
    <div className="space-y-1">
      <p className="text-muted-foreground">{label}</p>
      <pre
        className={`max-h-28 overflow-auto rounded border p-2 whitespace-pre-wrap ${
          wrong ? "border-rose-300 bg-rose-50 dark:border-rose-900 dark:bg-rose-950/40" : "bg-muted/40"
        }`}
      >
        {value === "" ? <span className="text-muted-foreground">(trống)</span> : value}
      </pre>
    </div>
  );
}
