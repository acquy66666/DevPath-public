"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Clock,
  CodeXml,
  Cpu,
  FileCode,
  ListChecks,
  Maximize2,
  Minimize2,
  Play,
  RotateCcw,
  Send,
} from "lucide-react";
import dynamic from "next/dynamic";
import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from "react";

import type { CodeEditorHandle } from "@/components/exercise/code-editor";
import { RunResult } from "@/components/exercise/run-result";
import { SubmissionHistory } from "@/components/exercise/submission-history";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Markdown } from "@/components/ui/markdown";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api/client";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { getExerciseOfLesson } from "@/lib/api/grading";
import {
  createSubmission,
  createTrialRun,
  getSubmission,
  isFinished,
  listSampleTestCases,
  listSubmissions,
  watchSubmission,
  type GradingEvent,
  type Submission,
} from "@/lib/api/submissions";
import { formatDateTime } from "@/lib/format";
import { formatLimit, languageLabel } from "@/lib/grading/result-view";
import { mergeCaseReport, type CaseReports } from "@/lib/grading/run-progress";
import { cn } from "@/lib/utils";

/**
 * Monaco is a megabyte of editor and it renders nothing on the server.
 *
 * `ssr: false` is not an optimisation here — the editor touches `document` at
 * import time, so rendering it on the server is an error rather than a waste.
 */
const CodeEditor = dynamic(
  () => import("@/components/exercise/code-editor").then((m) => m.CodeEditor),
  {
    ssr: false,
    loading: () => <Skeleton className="h-80 rounded-none sm:h-[420px]" />,
  },
);

/** Where an unfinished attempt is kept between visits. */
function draftKey(exerciseId: string): string {
  return `devpath:code:${exerciseId}`;
}

const REDUCE = "(prefers-reduced-motion: reduce)";

/**
 * The student's side of a code exercise: read it, write it, try it, hand it in.
 *
 * The two buttons do almost the same thing and mean very different things.
 * "Chạy thử" runs against the sample cases and leaves no trace; "Nộp bài" is
 * an attempt, judged against every case, and it goes into the history below.
 * Both are graded by the same worker in the same sandbox, and both are watched
 * through the same channel — which is why there is one result component and
 * not two.
 *
 * Full screen is the same tree with other classes: statement on the left,
 * editor and result on the right. Nothing is mounted again on the way in or
 * out, so Monaco keeps its cursor and its undo stack.
 */
export function ExerciseWorkspace({
  lessonId,
  accessToken,
  onSolved,
  title,
  context,
}: {
  lessonId: string;
  accessToken: string;
  /** Every case passed on a real submission — the lesson is finished. */
  onSolved?: () => void;
  /** Lesson title and course title, for the bar of the full-screen view. */
  title?: string;
  context?: string;
}) {
  const queryClient = useQueryClient();
  const statementId = useId();

  const exercise = useQuery({
    queryKey: ["code-exercise", lessonId],
    queryFn: () => getExerciseOfLesson(lessonId, accessToken),
    retry: false,
  });
  const exerciseId = exercise.data?.id ?? null;

  const samples = useQuery({
    queryKey: ["test-case-samples", exerciseId],
    queryFn: () => listSampleTestCases(accessToken, exerciseId as string),
    enabled: exerciseId !== null,
  });

  const history = useQuery({
    queryKey: ["submissions", exerciseId],
    queryFn: () => listSubmissions(accessToken, exerciseId as string),
    enabled: exerciseId !== null,
  });

  // `null` until the editor has been given its starting text: Monaco is
  // uncontrolled (see code-editor.tsx), so the initial value has to be known
  // before it mounts rather than pushed in afterwards.
  const [code, setCode] = useState<string | null>(null);
  const editor = useRef<CodeEditorHandle>(null);
  // Which run is on screen, and whether it is still moving. `watchId` is set
  // only for a run this page just started: picking an old submission out of
  // the history has nothing left to watch.
  const [shownId, setShownId] = useState<string | null>(null);
  const [shownTrial, setShownTrial] = useState(false);
  const [watchId, setWatchId] = useState<string | null>(null);
  const [event, setEvent] = useState<GradingEvent | null>(null);
  // What each case came back as, kept alongside the latest event rather than
  // inside it: an event is a moment, and the list is everything the grader has
  // said so far. Only the live channel names cases, so on the polling fallback
  // this stays empty and the list waits instead of moving.
  const [reports, setReports] = useState<CaseReports>([]);
  const [failure, setFailure] = useState<string | null>(null);
  const [focused, setFocused] = useState(false);
  // Bumped whenever a result is put on screen, to bring it into view.
  const [reveal, setReveal] = useState(0);
  const resultTop = useRef<HTMLDivElement>(null);
  const enter = useRef<HTMLButtonElement>(null);
  const wasFocused = useRef(false);
  // Whether the run being watched is a rehearsal. In a ref rather than in
  // state because the watcher's callback reads it long after the render that
  // started the run, and a trial mistaken for a submission would tick a
  // lesson that has not met a single hidden case.
  const watchedTrial = useRef(false);
  // The parent's callback, kept where the effect can reach the current one
  // without listing it as a dependency -- an inline arrow is a new function
  // every render, and depending on it would tear the socket down and build it
  // again on each one.
  const solved = useRef(onSolved);
  useEffect(() => {
    solved.current = onSolved;
  }, [onSolved]);

  // Decide the editor's opening text once per exercise: the draft this student
  // left behind, or the starter code the instructor wrote, or nothing.
  const filledFor = useRef<string | null>(null);
  useEffect(() => {
    if (exerciseId === null || filledFor.current === exerciseId) return;
    filledFor.current = exerciseId;

    let draft: string | null = null;
    try {
      draft = window.localStorage.getItem(draftKey(exerciseId));
    } catch {
      // Private mode, or storage turned off. The starter code is a fine
      // second choice and losing a draft is not worth breaking the page over.
    }
    setCode(draft ?? exercise.data?.starter_code ?? "");
  }, [exerciseId, exercise.data?.starter_code]);

  const editCode = useCallback(
    (next: string) => {
      setCode(next);
      if (exerciseId === null) return;
      try {
        window.localStorage.setItem(draftKey(exerciseId), next);
      } catch {
        // See above: an unsaved draft is a smaller loss than a thrown render.
      }
    },
    [exerciseId],
  );

  // The live channel, or polling if it is not available — `watchSubmission`
  // decides which, and this component never learns the answer.
  useEffect(() => {
    if (watchId === null) return;

    const stop = watchSubmission({
      submissionId: watchId,
      accessToken,
      onEvent: (next) => {
        setEvent(next);
        setReports((known) => mergeCaseReport(known, next));
        if (!isFinished(next.status)) return;
        // The result itself lives at the REST endpoint: the event says it is
        // ready, and this is the fetch that goes and gets it.
        queryClient.invalidateQueries({ queryKey: ["submission", next.submission_id] });
        queryClient.invalidateQueries({ queryKey: ["submissions", exerciseId] });
        if (next.verdict === "AC" && !watchedTrial.current) solved.current?.();
      },
    });

    return stop;
  }, [watchId, accessToken, exerciseId, queryClient]);

  // Full screen: the page behind must not scroll under it, and leaving puts
  // the keyboard back on the button that opened it.
  useEffect(() => {
    if (focused) {
      wasFocused.current = true;
      const previous = document.body.style.overflow;
      document.body.style.overflow = "hidden";
      editor.current?.focus();
      return () => {
        document.body.style.overflow = previous;
      };
    }
    if (wasFocused.current) {
      wasFocused.current = false;
      enter.current?.focus();
    }
  }, [focused]);

  // A result that lands below the fold is a reaction nobody sees: bring its
  // band into view, unless it already is.
  useEffect(() => {
    const band = resultTop.current;
    if (reveal === 0 || !band) return;
    const box = band.getBoundingClientRect();
    if (box.top >= 0 && box.bottom <= window.innerHeight) return;
    band.scrollIntoView({
      block: "center",
      behavior: window.matchMedia(REDUCE).matches ? "auto" : "smooth",
    });
  }, [reveal]);

  const detail = useQuery({
    queryKey: ["submission", shownId],
    queryFn: () => getSubmission(shownId as string, accessToken),
    enabled: shownId !== null,
  });

  function started(submission: Submission) {
    setFailure(null);
    setShownId(submission.id);
    setShownTrial(submission.is_trial);
    setWatchId(submission.id);
    setEvent(null);
    setReports([]);
    setReveal((n) => n + 1);
    watchedTrial.current = submission.is_trial;
    if (!submission.is_trial) {
      queryClient.invalidateQueries({ queryKey: ["submissions", exerciseId] });
    }
  }

  function refused(error: unknown) {
    if (error instanceof ApiError && error.retryAfter !== null) {
      setFailure(`${error.message} (còn ${error.retryAfter} giây)`);
      return;
    }
    setFailure(apiErrorMessage(error));
  }

  const tryIt = useMutation({
    mutationFn: () => createTrialRun(accessToken, exerciseId as string, code ?? ""),
    onSuccess: started,
    onError: refused,
  });

  const submit = useMutation({
    mutationFn: () => createSubmission(accessToken, exerciseId as string, code ?? ""),
    onSuccess: started,
    onError: refused,
  });

  if (exercise.isError) {
    return (
      <Alert>
        <AlertDescription>{apiErrorMessage(exercise.error)}</AlertDescription>
      </Alert>
    );
  }

  if (!exercise.data) {
    return <Skeleton className="h-96 rounded-lg" />;
  }

  const sampleCases = (samples.data ?? []).filter((row) => !row.is_hidden);
  const hiddenCount = (samples.data ?? []).length - sampleCases.length;
  const busy = tryIt.isPending || submit.isPending;
  const grading =
    watchId !== null && event !== null && !isFinished(event.status);
  const empty = (code ?? "").trim() === "";
  const fileName = exercise.data.language === "python" ? "main.py" : "main";
  const reopened = detail.data && watchId !== shownId ? detail.data : null;

  const actions: ReactNode = (
    <>
      <Button
        variant="outline"
        className={cn(!focused && "h-11 sm:h-9")}
        onClick={() => tryIt.mutate()}
        disabled={busy || grading || empty || sampleCases.length === 0}
        title={sampleCases.length === 0 ? "Bài tập này không có test mẫu để chạy thử" : undefined}
      >
        <Play aria-hidden />
        Chạy thử
      </Button>
      <Button
        className={cn(!focused && "h-11 sm:h-9")}
        onClick={() => submit.mutate()}
        disabled={busy || grading || empty}
      >
        <Send aria-hidden />
        Nộp bài
      </Button>
    </>
  );

  return (
    <div
      role={focused ? "region" : undefined}
      aria-label={focused ? "Làm bài toàn màn hình" : undefined}
      onKeyDown={(e) => {
        // Monaco claims Escape for its own widgets and says so by preventing
        // the default; only an Escape nobody used leaves full screen.
        if (focused && e.key === "Escape" && !e.defaultPrevented) setFocused(false);
      }}
      className={focused ? "fixed inset-0 z-50 flex flex-col bg-background" : "flex flex-col gap-6"}
    >
      {focused ? (
        <div className="flex h-14 shrink-0 items-center gap-3 border-b border-border bg-card px-3">
          <Button variant="ghost" onClick={() => setFocused(false)}>
            <Minimize2 aria-hidden />
            Thoát toàn màn hình
          </Button>
          <span aria-hidden className="h-6 w-px bg-border" />
          <div className="flex min-w-0 flex-col">
            <p className="truncate text-title">{title ?? "Bài tập code"}</p>
            {context ? <p className="truncate text-caption text-muted-foreground">{context}</p> : null}
          </div>
          <div className="ml-auto flex items-center gap-2">
            <span className="hidden text-caption text-muted-foreground xl:inline">
              Bản nháp tự lưu trên trình duyệt này
            </span>
            {actions}
          </div>
        </div>
      ) : null}

      <div className={focused ? "flex min-h-0 flex-1 flex-col lg:flex-row" : "contents"}>
        <section
          aria-labelledby={statementId}
          className={cn(
            "flex flex-col gap-4 bg-card",
            focused
              ? "max-h-[40%] shrink-0 overflow-y-auto border-b border-border p-5 lg:max-h-none lg:w-[30rem] lg:border-r lg:border-b-0 lg:p-6"
              : "rounded-lg border border-border p-4 sm:p-5",
          )}
        >
          <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
            <h2 id={statementId} className="text-title">
              Đề bài
            </h2>
            <ul aria-label="Giới hạn" className="flex flex-wrap gap-1.5">
              <Limit icon={<CodeXml aria-hidden />}>{languageLabel(exercise.data.language)}</Limit>
              <Limit icon={<Clock aria-hidden />}>{formatLimit(exercise.data.time_limit_ms)} mỗi test</Limit>
              <Limit icon={<Cpu aria-hidden />}>{exercise.data.memory_limit_mb} MB</Limit>
              <Limit icon={<ListChecks aria-hidden />}>
                {sampleCases.length} test mẫu
                {hiddenCount > 0 ? ` · ${hiddenCount} test ẩn` : ""}
              </Limit>
            </ul>
          </div>

          <Markdown className="max-w-prose">{exercise.data.statement_md}</Markdown>

          {sampleCases.length > 0 ? (
            <div className="flex flex-col gap-2">
              <h3 className="text-body-sm font-semibold">Test mẫu</h3>
              <ul className={cn("grid gap-3", !focused && "sm:grid-cols-2")}>
                {sampleCases.map((sample) => (
                  <li key={sample.id} className="overflow-hidden rounded-md border border-border">
                    <p className="bg-muted px-3 py-1.5 text-caption font-semibold text-muted-foreground">
                      Test #{sample.position + 1}
                    </p>
                    <div className="grid grid-cols-2 divide-x divide-border">
                      <Sample label="Đầu vào" value={sample.sample_input ?? ""} />
                      <Sample label="Kết quả mong đợi" value={sample.sample_output ?? ""} />
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </section>

        <div className={focused ? "flex min-h-0 min-w-0 flex-1 flex-col" : "contents"}>
          <section
            aria-label="Bài làm của bạn"
            className={cn(
              "flex flex-col bg-card",
              focused ? "min-h-0 flex-1" : "overflow-hidden rounded-lg border border-border-strong",
            )}
          >
            <div className="flex h-12 shrink-0 items-center gap-2 border-b border-border bg-background pr-2">
              <span className="inline-flex h-full items-center gap-2 border-b-2 border-primary bg-card px-4 font-mono text-code-sm font-semibold">
                <FileCode className="size-4 text-primary" aria-hidden />
                {fileName}
              </span>
              {focused ? null : (
                <span className="hidden truncate text-caption text-muted-foreground sm:inline">
                  Bản nháp tự lưu trên trình duyệt này
                </span>
              )}
              <Button
                size="sm"
                variant="ghost"
                className="ml-auto"
                onClick={() => editor.current?.setValue(exercise.data?.starter_code ?? "")}
                disabled={busy}
              >
                <RotateCcw aria-hidden />
                <span className="sr-only sm:not-sr-only">Khôi phục code mẫu</span>
              </Button>
              {focused ? null : (
                <Button
                  ref={enter}
                  size="icon-sm"
                  variant="ghost"
                  className="hidden lg:inline-flex"
                  aria-label="Toàn màn hình"
                  onClick={() => setFocused(true)}
                >
                  <Maximize2 aria-hidden />
                </Button>
              )}
            </div>

            {code === null ? (
              <Skeleton className={cn("rounded-none", focused ? "min-h-0 flex-1" : "h-80 sm:h-[420px]")} />
            ) : (
              <CodeEditor
                ref={editor}
                initialValue={code}
                onChange={editCode}
                language={exercise.data.language}
                className={focused ? "h-auto min-h-0 flex-1 sm:h-auto" : undefined}
              />
            )}

            {focused ? null : (
              <div className="flex flex-col gap-2 border-t border-border bg-background p-3 sm:flex-row sm:items-center sm:gap-3">
                <div className="grid grid-cols-2 gap-2 sm:order-2 sm:flex">{actions}</div>
                <p className="text-caption text-muted-foreground sm:order-1 sm:flex-1">
                  {sampleCases.length > 0
                    ? `“Chạy thử” chỉ dùng ${sampleCases.length} test mẫu và không vào lịch sử.`
                    : "Bài tập này không có test mẫu để chạy thử."}
                  <span className="sm:hidden"> Bản nháp tự lưu trên trình duyệt này.</span>
                </p>
              </div>
            )}
          </section>

          <div
            className={
              focused
                ? "flex h-[42%] shrink-0 flex-col gap-6 overflow-y-auto border-t border-border-strong bg-background px-5 py-4"
                : "contents"
            }
          >
            {failure !== null ? (
              <Alert variant="destructive">
                <AlertDescription>{failure}</AlertDescription>
              </Alert>
            ) : null}

            {shownId !== null ? (
              <section className="flex flex-col gap-2.5" aria-label="Kết quả">
                <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
                  <h2 className="text-title">Kết quả</h2>
                  {/* Only for a run that is over and is not the one being
                      watched: dropping an old answer into the editor
                      mid-grading would be a surprise, and doing it to the code
                      that is currently running would be one too. */}
                  {reopened ? (
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                      <p className="text-body-sm text-muted-foreground">
                        Xem lại bài nộp lúc{" "}
                        <time className="tabular-nums" dateTime={reopened.created_at}>
                          {formatDateTime(reopened.created_at)}
                        </time>
                      </p>
                      <Button size="sm" variant="ghost" onClick={() => editor.current?.setValue(reopened.code)}>
                        <FileCode aria-hidden />
                        Đưa code này vào editor
                      </Button>
                    </div>
                  ) : null}
                </div>
                <RunResult
                  // A fresh panel per run: which rows are open belongs to the
                  // run they were opened on.
                  key={shownId}
                  ref={resultTop}
                  event={watchId === shownId ? event : null}
                  reports={watchId === shownId ? reports : []}
                  detail={detail.data ?? null}
                  cases={samples.data ?? []}
                  trial={detail.data?.is_trial ?? shownTrial}
                  reactTo={watchId === shownId && !shownTrial ? shownId : null}
                  limits={{
                    timeMs: exercise.data.time_limit_ms,
                    memoryMb: exercise.data.memory_limit_mb,
                  }}
                  language={exercise.data.language}
                />
              </section>
            ) : null}

            <section className="flex flex-col gap-2.5" aria-label="Lịch sử nộp bài">
              <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                <h2 className="text-title">Lịch sử nộp bài</h2>
                {history.data && history.data.total > 0 ? (
                  <p className="text-caption text-muted-foreground">
                    {history.data.total} lần nộp · chạy thử không tính
                  </p>
                ) : null}
              </div>
              <SubmissionHistory
                submissions={history.data?.items ?? []}
                selectedId={shownId}
                onSelect={(submission) => {
                  setShownId(submission.id);
                  setShownTrial(submission.is_trial);
                  // Nothing to watch: this one finished long ago. Clearing the
                  // watcher is also what stops a live run's progress bar from
                  // being painted over an old submission's result.
                  setWatchId(null);
                  setEvent(null);
                  setReports([]);
                  setReveal((n) => n + 1);
                }}
              />
            </section>
          </div>
        </div>
      </div>
    </div>
  );
}

function Limit({ icon, children }: { icon: ReactNode; children: ReactNode }) {
  return (
    <li>
      <Badge variant="muted" className="font-medium">
        {icon}
        {children}
      </Badge>
    </li>
  );
}

function Sample({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex min-w-0 flex-col gap-1 p-3">
      <p className="text-caption text-muted-foreground">{label}</p>
      <pre className="font-mono text-code-sm whitespace-pre-wrap break-words">
        {value === "" ? <span className="text-muted-foreground">(trống)</span> : value}
      </pre>
    </div>
  );
}
