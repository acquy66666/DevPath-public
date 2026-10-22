"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileCode2, Play, RotateCcw, Send } from "lucide-react";
import dynamic from "next/dynamic";
import { useCallback, useEffect, useRef, useState } from "react";

import type { CodeEditorHandle } from "@/components/exercise/code-editor";
import { RunResult } from "@/components/exercise/run-result";
import { SubmissionHistory } from "@/components/exercise/submission-history";
import { Alert, AlertDescription } from "@/components/ui/alert";
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
import { mergeCaseReport, type CaseReports } from "@/lib/grading/run-progress";

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
    loading: () => <Skeleton className="h-[420px]" />,
  },
);

/** Where an unfinished attempt is kept between visits. */
function draftKey(exerciseId: string): string {
  return `devpath:code:${exerciseId}`;
}

/**
 * The student's side of a code exercise: read it, write it, try it, hand it in.
 *
 * The two buttons do almost the same thing and mean very different things.
 * "Chạy thử" runs against the sample cases and leaves no trace; "Nộp bài" is
 * an attempt, judged against every case, and it goes into the history below.
 * Both are graded by the same worker in the same sandbox, and both are watched
 * through the same channel — which is why there is one result component and
 * not two.
 */
export function ExerciseWorkspace({
  lessonId,
  accessToken,
  onSolved,
}: {
  lessonId: string;
  accessToken: string;
  /** Every case passed on a real submission — the lesson is finished. */
  onSolved?: () => void;
}) {
  const queryClient = useQueryClient();

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
  const [watchId, setWatchId] = useState<string | null>(null);
  const [event, setEvent] = useState<GradingEvent | null>(null);
  // What each case came back as, kept alongside the latest event rather than
  // inside it: an event is a moment, and the list is everything the grader has
  // said so far. Only the live channel names cases, so on the polling fallback
  // this stays empty and the list waits instead of moving.
  const [reports, setReports] = useState<CaseReports>([]);
  const [failure, setFailure] = useState<string | null>(null);
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

  const detail = useQuery({
    queryKey: ["submission", shownId],
    queryFn: () => getSubmission(shownId as string, accessToken),
    enabled: shownId !== null,
  });

  function started(submission: Submission) {
    setFailure(null);
    setShownId(submission.id);
    setWatchId(submission.id);
    setEvent(null);
    setReports([]);
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

  return (
    <div className="space-y-6">
      <section className="space-y-3 rounded-lg border p-4">
        <Markdown className="text-sm">{exercise.data.statement_md}</Markdown>
        <p className="text-xs text-muted-foreground">
          Giới hạn: {exercise.data.time_limit_ms} ms ·{" "}
          {exercise.data.memory_limit_mb} MB · {sampleCases.length} test mẫu
          {hiddenCount > 0 ? ` · ${hiddenCount} test ẩn` : ""}
        </p>
      </section>

      {sampleCases.length > 0 ? (
        <section className="space-y-2">
          <h2 className="text-sm font-semibold">Test case mẫu</h2>
          <ul className="grid gap-2 sm:grid-cols-2">
            {sampleCases.map((sample) => (
              <li key={sample.id} className="space-y-1 rounded-md border p-3 text-xs">
                <p className="text-muted-foreground">Input</p>
                <pre className="overflow-x-auto rounded bg-muted/40 p-2 whitespace-pre-wrap">
                  {sample.sample_input || "(trống)"}
                </pre>
                <p className="text-muted-foreground">Kết quả mong đợi</p>
                <pre className="overflow-x-auto rounded bg-muted/40 p-2 whitespace-pre-wrap">
                  {sample.sample_output || "(trống)"}
                </pre>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="space-y-3">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-sm font-semibold">Bài làm của bạn</h2>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => editor.current?.setValue(exercise.data?.starter_code ?? "")}
            disabled={busy}
          >
            <RotateCcw aria-hidden />
            Khôi phục code mẫu
          </Button>
        </div>

        {code === null ? (
          <Skeleton className="h-[420px]" />
        ) : (
          <CodeEditor
            ref={editor}
            initialValue={code}
            onChange={editCode}
            language={exercise.data.language}
          />
        )}

        <div className="flex flex-wrap items-center gap-3">
          <Button
            variant="outline"
            onClick={() => tryIt.mutate()}
            disabled={busy || grading || (code ?? "").trim() === "" || sampleCases.length === 0}
            title={
              sampleCases.length === 0
                ? "Bài tập này không có test mẫu để chạy thử"
                : undefined
            }
          >
            <Play aria-hidden />
            Chạy thử
          </Button>
          <Button
            onClick={() => submit.mutate()}
            disabled={busy || grading || (code ?? "").trim() === ""}
          >
            <Send aria-hidden />
            Nộp bài
          </Button>
          <p className="text-xs text-muted-foreground">
            “Chạy thử” chỉ chấm với test mẫu và không tính vào lịch sử.
          </p>
        </div>

        {failure !== null ? (
          <Alert variant="destructive">
            <AlertDescription>{failure}</AlertDescription>
          </Alert>
        ) : null}
      </section>

      {shownId !== null ? (
        <section className="space-y-2">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-sm font-semibold">Kết quả</h2>
            {/* Only for a run that is over and is not the one being watched:
                dropping an old answer into the editor mid-grading would be a
                surprise, and doing it to the code that is currently running
                would be one too. */}
            {detail.data && watchId !== shownId ? (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => editor.current?.setValue(detail.data.code)}
              >
                <FileCode2 aria-hidden />
                Đưa code này vào editor
              </Button>
            ) : null}
          </div>
          <RunResult
            event={watchId === shownId ? event : null}
            reports={watchId === shownId ? reports : []}
            detail={detail.data ?? null}
            samples={samples.data ?? []}
            trial={detail.data?.is_trial ?? false}
          />
        </section>
      ) : null}

      <section className="space-y-2">
        <h2 className="text-sm font-semibold">Lịch sử nộp bài</h2>
        <SubmissionHistory
          submissions={history.data?.items ?? []}
          selectedId={shownId}
          onSelect={(submission) => {
            setShownId(submission.id);
            // Nothing to watch: this one finished long ago. Clearing the
            // watcher is also what stops a live run's progress bar from being
            // painted over an old submission's result.
            setWatchId(null);
            setEvent(null);
            setReports([]);
          }}
        />
      </section>
    </div>
  );
}
