"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { LockKeyhole } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { AttemptHistory } from "@/components/quiz/attempt-history";
import { QuizIntro } from "@/components/quiz/quiz-intro";
import { preloadResultMoods, QuizResult } from "@/components/quiz/quiz-result";
import { QuizSheet } from "@/components/quiz/quiz-sheet";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Skeleton, SkeletonRegion, SkeletonText } from "@/components/ui/skeleton";
import { apiErrorMessage } from "@/lib/api/error-messages";
import {
  getAttempt,
  getQuizOfLesson,
  listAttempts,
  startAttempt,
  submitAttempt,
  type Attempt,
} from "@/lib/api/quiz";
import { historyRows, resultCopy, summarizeReview, timerAnnouncement } from "@/lib/quiz/result-view";

const REDUCE = "(prefers-reduced-motion: reduce)";

// The answers of a running attempt, kept in this browser until it is handed
// in. The server stores answers only on submit, so without this a refresh in
// the middle of a timed quiz would cost every answer while the clock ran on.
// A convenience for this viewer only: unreadable or missing is simply blank.
const draftKey = (attemptId: string) => `devpath:quiz-draft:${attemptId}`;

function readDraft(attempt: Attempt): (number | null)[] | null {
  try {
    const raw = window.localStorage.getItem(draftKey(attempt.id));
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed) || parsed.length !== attempt.questions.length) return null;
    return parsed.map((value, index) =>
      Number.isInteger(value) && value >= 0 && value < attempt.questions[index].options.length
        ? (value as number)
        : null,
    );
  } catch {
    return null;
  }
}

function writeDraft(attemptId: string, answers: (number | null)[]) {
  try {
    window.localStorage.setItem(draftKey(attemptId), JSON.stringify(answers));
  } catch {
    // Storage full, blocked or absent: the answers still live on the page.
  }
}

function dropDraft(attemptId: string) {
  try {
    window.localStorage.removeItem(draftKey(attemptId));
  } catch {
    // Nothing to clean up, or nothing we may touch.
  }
}

/** Where focus goes once the next screen of the quiz is on the page. */
type FocusTarget = "paper" | "result" | "start";

/**
 * The student's side of a quiz: start it, answer it, hand it in, read why.
 *
 * The countdown on this page is a *display of* the deadline, not the deadline
 * itself. It is seeded from `seconds_remaining`, which the server computes
 * against its own clock, and reaching zero here submits the paper rather than
 * deciding anything about it -- if this tab were paused, throttled or frozen,
 * the server would still refuse the answers. That is the whole reason the
 * component is allowed to be this simple.
 *
 * It deliberately does not start an attempt on mount. Opening a lesson to see
 * what is in it must not start a clock; the student presses the button, and
 * the button says "tiếp tục" when there is an unfinished attempt to resume.
 *
 * Naomi answers the attempt handed in on this page, once (`reactTo`). One
 * opened again from the history is a still picture.
 */
export function QuizWorkspace({
  lessonId,
  accessToken,
  finished,
  review,
  onPassed,
  onSittingChange,
}: {
  lessonId: string;
  accessToken: string;
  /** The lesson is ticked: "Bài tiếp theo" is the main button, not this. */
  finished: boolean;
  /** The first lesson of the quiz's chapter, for "Ôn lại chương N". */
  review: { href: string; label: string } | null;
  /** The quiz was passed -- the lesson is finished, in the same transaction. */
  onPassed?: () => void;
  /** An attempt is being answered: the page keeps its other buttons quiet. */
  onSittingChange?: (sitting: boolean) => void;
}) {
  const queryClient = useQueryClient();

  const quiz = useQuery({
    queryKey: ["quiz", lessonId],
    queryFn: () => getQuizOfLesson(lessonId, accessToken),
    retry: false,
  });
  const quizId = quiz.data?.id ?? null;

  const attempts = useQuery({
    queryKey: ["quiz-attempts", quizId],
    queryFn: () => listAttempts(accessToken, quizId as string),
    enabled: quizId !== null,
  });

  const [attempt, setAttempt] = useState<Attempt | null>(null);
  const [answers, setAnswers] = useState<(number | null)[]>([]);
  const [remaining, setRemaining] = useState<number | null>(null);
  const [reactTo, setReactTo] = useState<string | null>(null);
  //: Guards the one submit the countdown makes on its own, so a re-render at
  //: zero cannot fire a second one.
  const handedIn = useRef(false);
  const focusNext = useRef<FocusTarget | null>(null);
  const band = useRef<HTMLDivElement>(null);
  const firstQuestion = useRef<HTMLFieldSetElement>(null);
  const startButton = useRef<HTMLButtonElement>(null);

  const running = attempt !== null && attempt.submitted_at === null;

  function adopt(next: Attempt, focus: FocusTarget) {
    setAttempt(next);
    setRemaining(next.submitted_at === null ? next.seconds_remaining : null);
    setAnswers(
      next.review
        ? next.review.map((row) => row.your_answer)
        : (readDraft(next) ?? Array<number | null>(next.questions.length).fill(null)),
    );
    focusNext.current = focus;
  }

  function refreshHistory() {
    queryClient.invalidateQueries({ queryKey: ["quiz-attempts", quizId] });
  }

  const begin = useMutation({
    mutationFn: () => startAttempt(accessToken, quizId as string),
    onSuccess: (next) => {
      handedIn.current = false;
      setReactTo(null);
      adopt(next, "paper");
      refreshHistory();
    },
  });

  const hand = useMutation({
    mutationFn: (chosen: (number | null)[]) =>
      submitAttempt(accessToken, attempt?.id as string, chosen),
    onSuccess: (next) => {
      dropDraft(next.id);
      setReactTo(next.id);
      adopt(next, "result");
      refreshHistory();
      // A paper handed in is a day of study, passed or not.
      queryClient.invalidateQueries({ queryKey: ["gamification"] });
      if (next.passed) onPassed?.();
    },
  });

  const reopen = useMutation({
    mutationFn: (attemptId: string) => getAttempt(accessToken, attemptId),
    onSuccess: (next) => {
      setReactTo(null);
      adopt(next, "result");
    },
  });

  // One tick per second while an attempt is running and timed.
  useEffect(() => {
    if (!running || remaining === null || remaining <= 0) return;
    const timer = setTimeout(() => setRemaining((left) => (left === null ? null : left - 1)), 1000);
    return () => clearTimeout(timer);
  }, [running, remaining]);

  // Out of time: hand in whatever is on the page. Anything the server judges
  // to be past the grace window comes back marked zero, and the result says
  // so -- the page does not decide that here.
  useEffect(() => {
    if (running && remaining === 0 && !handedIn.current && !hand.isPending) {
      handedIn.current = true;
      hand.mutate(answers);
    }
  }, [running, remaining, answers, hand]);

  useEffect(() => {
    if (running && attempt) writeDraft(attempt.id, answers);
  }, [running, attempt, answers]);

  useEffect(() => {
    onSittingChange?.(running);
    return () => onSittingChange?.(false);
  }, [running, onSittingChange]);

  // The result must not wait on a download when it lands.
  useEffect(() => {
    if (running) preloadResultMoods();
  }, [running]);

  // The button that was pressed is gone with the screen it was on: put focus
  // where the next screen starts, and bring a result into view (the hand-in
  // is at the bottom of a long paper, the result at its top).
  useEffect(() => {
    const target = focusNext.current;
    if (target === null) return;
    focusNext.current = null;
    if (target === "paper") {
      firstQuestion.current?.focus();
    } else if (target === "start") {
      startButton.current?.focus();
    } else if (band.current) {
      band.current.focus({ preventScroll: true });
      band.current.scrollIntoView({
        block: "start",
        behavior: window.matchMedia(REDUCE).matches ? "auto" : "smooth",
      });
    }
  }, [attempt]);

  if (quiz.isPending) {
    return (
      <SkeletonRegion
        label="Đang tải bài trắc nghiệm"
        className="flex flex-col gap-5 rounded-lg border bg-card p-5 sm:p-6"
      >
        <div className="flex items-center gap-4">
          <Skeleton className="size-12 shrink-0 rounded-lg" />
          <div className="flex w-full max-w-72 flex-col">
            <SkeletonText size="h3" className="w-44" />
            <SkeletonText size="body-sm" />
          </div>
        </div>
        <div className="grid grid-cols-3 gap-2 sm:gap-3">
          <Skeleton className="h-16 sm:h-18" />
          <Skeleton className="h-16 sm:h-18" />
          <Skeleton className="h-16 sm:h-18" />
        </div>
        <Skeleton className="h-11 w-full sm:w-44" />
      </SkeletonRegion>
    );
  }

  if (quiz.isError) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{apiErrorMessage(quiz.error)}</AlertDescription>
      </Alert>
    );
  }

  const meta = quiz.data;
  if (!meta.is_published || meta.question_count === 0) {
    return (
      <div className="flex items-center gap-4 rounded-lg border bg-card p-5 sm:p-6">
        <span
          aria-hidden
          className="flex size-12 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground"
        >
          <LockKeyhole className="size-6" />
        </span>
        <div className="flex min-w-0 flex-col gap-0.5">
          <h2 className="text-title">Bài trắc nghiệm này chưa được mở</h2>
          <p className="text-body-sm text-muted-foreground">
            Giảng viên chưa xuất bản câu hỏi. Bạn vẫn học tiếp được các bài khác.
          </p>
        </div>
      </div>
    );
  }

  const history = attempts.data ? historyRows(attempts.data) : null;
  const historyPanel = history ? (
    <AttemptHistory
      history={history}
      viewing={attempt?.id ?? null}
      opening={reopen.isPending ? (reopen.variables ?? null) : null}
      onOpen={(attemptId) => reopen.mutate(attemptId)}
    />
  ) : null;

  let body;
  let announce = "";

  if (attempt === null) {
    body = (
      <>
        <QuizIntro
          quiz={meta}
          history={history}
          finished={finished}
          starting={begin.isPending}
          error={begin.isError ? apiErrorMessage(begin.error) : null}
          onStart={() => begin.mutate()}
          startRef={startButton}
        />
        {reopen.isError ? (
          <Alert variant="destructive">
            <AlertDescription>{apiErrorMessage(reopen.error)}</AlertDescription>
          </Alert>
        ) : null}
        {historyPanel}
      </>
    );
  } else if (attempt.review) {
    const justHandedIn = reactTo === attempt.id;
    if (justHandedIn) {
      const summary = summarizeReview(attempt.review, attempt.expired);
      const copy = resultCopy({
        score: attempt.score ?? 0,
        passed: attempt.passed === true,
        expired: attempt.expired,
        passScore: attempt.pass_score,
        correct: summary.correct,
        total: summary.total,
        timeLimitS: attempt.time_limit_s,
      });
      announce = `${attempt.score ?? 0}%. ${copy.chip}. ${copy.headline}.`;
    }
    body = (
      <>
        <QuizResult
          attempt={attempt}
          number={history?.rows.find((row) => row.id === attempt.id)?.number ?? null}
          reactTo={reactTo}
          finished={finished}
          review={review}
          onRetry={() => begin.mutate()}
          retrying={begin.isPending}
          retryError={begin.isError ? apiErrorMessage(begin.error) : null}
          onClose={
            justHandedIn
              ? null
              : () => {
                  focusNext.current = "start";
                  setAttempt(null);
                }
          }
          bandRef={band}
        />
        {historyPanel}
      </>
    );
  } else {
    const limit = attempt.time_limit_s;
    if (remaining !== null && limit !== null) announce = timerAnnouncement(remaining, limit) ?? "";
    body = (
      <QuizSheet
        questions={attempt.questions}
        answers={answers}
        onChoose={(question, option) =>
          setAnswers((current) => current.map((value, index) => (index === question ? option : value)))
        }
        remaining={remaining}
        limit={limit}
        submitting={hand.isPending}
        error={hand.isError ? apiErrorMessage(hand.error) : null}
        onSubmit={() => hand.mutate(answers)}
        firstRef={firstQuestion}
      />
    );
  }

  return (
    <div className="flex flex-col gap-4 sm:gap-5">
      {body}
      {/* One live region for the quiz's whole life on the page, so a screen
          reader hears the clock's warnings and then the score: a region that
          mounts with its text already in it is not announced. */}
      <p className="sr-only" aria-live="polite">
        {announce}
      </p>
    </div>
  );
}
