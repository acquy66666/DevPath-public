"use client";

import { ArrowDown } from "lucide-react";
import { useEffect, type ReactNode, type Ref } from "react";

import { CaseBar, CaseList } from "@/components/exercise/case-list";
import { VerdictChip } from "@/components/exercise/verdict-chip";
import { Mascot, preloadMascot } from "@/components/mascot/mascot";
import { Badge } from "@/components/ui/badge";
import type {
  GradingEvent,
  SubmissionDetail,
  TestCaseSample,
} from "@/lib/api/submissions";
import {
  type CaseRow,
  finishedRows,
  firstProblem,
  formatLimit,
  formatSeconds,
  liveRows,
  queuedRows,
  summarize,
} from "@/lib/grading/result-view";
import { caseSlots, type CaseReports } from "@/lib/grading/run-progress";
import {
  VERDICT_CLASSES,
  VERDICT_HINTS,
  VERDICT_LABELS,
  VERDICT_MOOD,
  asVerdict,
} from "@/lib/grading/verdicts";
import { cn } from "@/lib/utils";

const NAOMI = "size-20 sm:size-32";

/**
 * What one run did, while it does it and after it is finished.
 *
 * Two sources feed this and they are deliberately not merged into one state:
 * `event` is the live progress (or the polled snapshot — the client cannot
 * tell), and `detail` is the finished result read from the REST endpoint. The
 * first says how far along; only the second carries a sample's output, because
 * the live channel has no field for output at all. The case list is the same
 * list at both moments, at two levels of detail.
 *
 * Naomi answers a submission, never a trial run: rehearsals stay quiet so that
 * her reaction means something. She reacts only to the run this page just
 * started (`reactTo`); a result reopened from the history is a still picture.
 */
export function RunResult({
  event,
  reports,
  detail,
  cases,
  trial,
  reactTo,
  limits,
  language,
  ref,
}: {
  event: GradingEvent | null;
  reports: CaseReports;
  detail: SubmissionDetail | null;
  /** Every case of the exercise (samples with their data, hidden ones without). */
  cases: TestCaseSample[];
  trial: boolean;
  /** The submission Naomi answers, once; null for a still picture. */
  reactTo: string | null;
  limits: { timeMs: number; memoryMb: number };
  language: string;
  /** The band at the top, for scrolling the result into view. */
  ref?: Ref<HTMLDivElement>;
}) {
  // The event first: while a run is going it is fresher than a detail that
  // was fetched when the run started. A history pick has no event and falls
  // through to the row it was asked about.
  const status = event?.status ?? detail?.status ?? "pending";
  const running = status === "pending" || status === "running";
  const naomi = !trial;

  // Her answer to the verdict must not wait on a download when it lands.
  useEffect(() => {
    if (running && naomi && reactTo !== null) preloadMascot(...Object.values(VERDICT_MOOD));
  }, [running, naomi, reactTo]);

  if (running) {
    const slots = caseSlots(event, reports, cases);
    const rows = slots.length > 0 ? liveRows(slots) : queuedRows(cases, trial);
    const total = event?.total_cases || rows.length;
    const done = event?.completed_cases ?? 0;
    // Which case is on the grader's bench: the one after everything finished,
    // except at the very end, where the last case is done and the verdict is
    // being written — no case is running then, and "test 11/10" would be a lie
    // told by arithmetic.
    const current = Math.min(done + 1, total);
    const title =
      status === "pending"
        ? "Đang chờ tới lượt chấm…"
        : total > 0
          ? `Đang chấm test ${current}/${total}`
          : "Đang chấm…";

    return (
      <Shell announce={title}>
        <div ref={ref} className="flex items-center gap-3.5 rounded-lg bg-muted p-3.5 sm:gap-5 sm:p-5">
          {naomi ? (
            <Mascot
              mood="grading"
              event={reactTo}
              progress={total > 0 ? done / total : 0}
              className={NAOMI}
            />
          ) : null}
          <div className="flex min-w-0 flex-1 flex-col gap-2">
            <p className="text-eyebrow text-muted-foreground uppercase">
              {trial ? "Chạy thử" : "Nộp bài"} · {status === "pending" ? "trong hàng đợi" : "đang chấm"}
            </p>
            <p className="text-h3 tabular-nums">{title}</p>
            <p className="text-body-sm text-muted-foreground">
              {status === "pending"
                ? "Bài của bạn được chấm ngay khi tới lượt."
                : `Mỗi test chạy trong một sandbox riêng: không có mạng, tối đa ${formatLimit(limits.timeMs)} và ${limits.memoryMb} MB.`}
            </p>
            <div className="pt-1">
              <CaseBar rows={rows} />
            </div>
          </div>
        </div>
        <Cases rows={rows} trial={trial} />
      </Shell>
    );
  }

  // The platform failed, not the submission. The sandbox rules say this is
  // never charged to the student, and the wording is where that shows up.
  if (status === "error") {
    const hint =
      detail?.message ??
      "Hệ thống chấm bài gặp sự cố. Bài của bạn chưa được chấm — thử lại sau ít phút nhé.";
    return (
      <Shell announce={`${VERDICT_LABELS.SE}. ${hint}`}>
        <Band
          bandRef={ref}
          letter="SE"
          naomi={naomi}
          reactTo={reactTo}
          trial={trial}
          title={VERDICT_LABELS.SE}
          hint={hint}
          meta="Lần nộp này không tính điểm."
        />
      </Shell>
    );
  }

  const letter = asVerdict(event?.verdict ?? detail?.verdict ?? null) ?? "SE";
  const rows = detail
    ? finishedRows(detail.results, cases)
    : liveRows(caseSlots(event, reports, cases));
  const summary = summarize(rows);
  const score = event?.score ?? detail?.score ?? null;
  const hiddenCount = cases.filter((row) => row.is_hidden).length;
  const first = letter === "AC" ? null : summary.firstFailing;

  const title = trial
    ? rows.length > 0
      ? `Chạy thử · ${summary.passed}/${rows.length} test mẫu đúng`
      : `Chạy thử · ${VERDICT_LABELS[letter]}`
    : score !== null
      ? `${score}/100 · ${VERDICT_LABELS[letter]}`
      : VERDICT_LABELS[letter];
  const hint =
    trial && letter === "AC" && hiddenCount > 0
      ? `Bấm “Nộp bài” để chấm với cả ${hiddenCount} test ẩn.`
      : VERDICT_HINTS[letter];
  const meta =
    rows.length > 0
      ? `${summary.passed}/${rows.length} test đúng${
          summary.slowestMs === null ? "" : ` · chậm nhất ${formatSeconds(summary.slowestMs)}`
        }`
      : letter === "CE"
        ? "Không test nào được chạy"
        : null;

  return (
    <Shell announce={title}>
      <Band
        bandRef={ref}
        letter={letter}
        naomi={naomi}
        reactTo={reactTo}
        trial={trial}
        title={title}
        hint={hint}
        pointer={first ? firstProblem(first) : null}
        meta={meta}
        rows={rows}
      />

      {/* A compile error has no per-case results: the program never became a
          program. The compiler's own words are the only thing to show. */}
      {detail?.message ? (
        <div className="flex flex-col gap-1.5">
          <p className="text-body-sm font-semibold">
            {letter === "CE"
              ? `Thông báo của ${language === "python" ? "Python" : "trình biên dịch"}`
              : "Thông báo của hệ thống chấm"}
          </p>
          <pre
            className={cn(
              "max-h-48 overflow-auto rounded-lg border bg-muted px-3.5 py-3 font-mono text-code-sm whitespace-pre-wrap",
              letter === "CE" ? VERDICT_CLASSES.CE.border : "border-border",
            )}
          >
            {detail.message}
          </pre>
        </div>
      ) : null}

      <Cases
        rows={rows}
        trial={trial}
        highlight={first?.label ?? null}
        openFirst={first && first.isHidden === false ? first.label : null}
      />
    </Shell>
  );
}

/**
 * One live region for the whole life of a run, so a screen reader hears the
 * count move and then the verdict -- a region that mounts with its text
 * already in it is not announced, and the band is replaced when the run ends.
 * The title only, not the hint: the golden flow finds the hint by its text,
 * and two elements holding it would be one too many.
 */
function Shell({ announce, children }: { announce: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-3">
      {children}
      <p className="sr-only" aria-live="polite">
        {announce}
      </p>
    </div>
  );
}

/** The verdict as a band in its own colour, with Naomi on a submission. */
function Band({
  bandRef,
  letter,
  naomi,
  reactTo,
  trial,
  title,
  hint,
  pointer = null,
  meta,
  rows = [],
}: {
  bandRef?: Ref<HTMLDivElement>;
  letter: keyof typeof VERDICT_CLASSES;
  naomi: boolean;
  reactTo: string | null;
  trial: boolean;
  title: string;
  hint: string;
  pointer?: string | null;
  meta: string | null;
  rows?: readonly CaseRow[];
}) {
  const tone = VERDICT_CLASSES[letter];
  const passed = rows.filter((row) => row.verdict === "AC").length;
  return (
    <div
      ref={bandRef}
      className={cn("flex items-center gap-3.5 rounded-lg p-3.5 sm:gap-5 sm:p-5", tone.soft)}
    >
      {naomi ? <Mascot mood={VERDICT_MOOD[letter]} event={reactTo} className={NAOMI} /> : null}
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <VerdictChip verdict={letter} surface="card" />
          {trial ? (
            <Badge variant="outline" className="bg-card">
              Chạy thử · không tính vào lịch sử
            </Badge>
          ) : null}
        </div>
        <p className={cn(trial ? "text-title" : "text-h3", "tabular-nums", tone.text)}>{title}</p>
        <p className="text-body-sm">{hint}</p>
        {pointer ? (
          <p className={cn("flex items-start gap-1.5 text-body-sm font-semibold", tone.text)}>
            <ArrowDown className="mt-0.5 size-4 shrink-0" aria-hidden />
            {pointer}
          </p>
        ) : null}
        {rows.length > 0 ? (
          <div className="pt-1">
            <CaseBar rows={rows} summary={`${passed}/${rows.length} test đúng`} />
          </div>
        ) : null}
        {meta ? <p className="text-caption text-muted-foreground tabular-nums">{meta}</p> : null}
      </div>
    </div>
  );
}

function Cases({
  rows,
  trial,
  highlight = null,
  openFirst = null,
}: {
  rows: readonly CaseRow[];
  trial: boolean;
  highlight?: number | null;
  openFirst?: number | null;
}) {
  if (rows.length === 0) return null;
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <p className="text-title">{trial ? "Test mẫu" : "Từng test"}</p>
        <p className="text-caption text-muted-foreground">
          {trial ? "Mở một test để so đầu ra." : "Test ẩn chỉ cho biết đúng hay sai."}
        </p>
      </div>
      <CaseList rows={rows} highlight={highlight} openFirst={openFirst} />
    </div>
  );
}
