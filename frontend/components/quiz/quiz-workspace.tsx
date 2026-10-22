"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Clock, ListChecks, XCircle } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { apiErrorMessage } from "@/lib/api/error-messages";
import {
  getQuizOfLesson,
  listAttempts,
  startAttempt,
  submitAttempt,
  type Attempt,
} from "@/lib/api/quiz";
import { cn } from "@/lib/utils";

/** mm:ss, the only formatting a countdown needs. */
function clock(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  return `${minutes}:${String(seconds % 60).padStart(2, "0")}`;
}

function describeLimit(seconds: number | null): string {
  if (seconds === null) return "không giới hạn thời gian";
  const minutes = Math.round(seconds / 60);
  return `${minutes} phút`;
}

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
 */
export function QuizWorkspace({
  lessonId,
  accessToken,
  onPassed,
}: {
  lessonId: string;
  accessToken: string;
  /** The quiz was passed -- the lesson is finished, in the same transaction. */
  onPassed?: () => void;
}) {
  const queryClient = useQueryClient();

  const quiz = useQuery({
    queryKey: ["quiz", lessonId],
    queryFn: () => getQuizOfLesson(lessonId, accessToken),
    retry: false,
  });
  const quizId = quiz.data?.id ?? null;

  const history = useQuery({
    queryKey: ["quiz-attempts", quizId],
    queryFn: () => listAttempts(accessToken, quizId as string),
    enabled: quizId !== null,
  });

  const [attempt, setAttempt] = useState<Attempt | null>(null);
  const [answers, setAnswers] = useState<(number | null)[]>([]);
  const [remaining, setRemaining] = useState<number | null>(null);
  //: Guards the one submit the countdown makes on its own, so a re-render at
  //: zero cannot fire a second one.
  const handedIn = useRef(false);

  const running = attempt !== null && attempt.submitted_at === null;

  const adopt = useCallback((next: Attempt) => {
    setAttempt(next);
    setRemaining(next.submitted_at === null ? next.seconds_remaining : null);
    setAnswers(
      next.review
        ? next.review.map((row) => row.your_answer)
        : Array<number | null>(next.questions.length).fill(null),
    );
  }, []);

  const begin = useMutation({
    mutationFn: () => startAttempt(accessToken, quizId as string),
    onSuccess: (next) => {
      handedIn.current = false;
      adopt(next);
    },
  });

  const hand = useMutation({
    mutationFn: (chosen: (number | null)[]) =>
      submitAttempt(accessToken, attempt?.id as string, chosen),
    onSuccess: (next) => {
      adopt(next);
      queryClient.invalidateQueries({ queryKey: ["quiz-attempts", quizId] });
      if (next.passed) onPassed?.();
    },
  });

  // One tick per second while an attempt is running and timed.
  useEffect(() => {
    if (!running || remaining === null || remaining <= 0) return;
    const timer = setTimeout(() => setRemaining((left) => (left === null ? null : left - 1)), 1000);
    return () => clearTimeout(timer);
  }, [running, remaining]);

  // Out of time: hand in whatever is on the page. Anything the server judges
  // to be past the grace window comes back marked zero, and the banner below
  // says so -- the page does not decide that here.
  useEffect(() => {
    if (running && remaining === 0 && !handedIn.current && !hand.isPending) {
      handedIn.current = true;
      hand.mutate(answers);
    }
  }, [running, remaining, answers, hand]);

  if (quiz.isPending) {
    return <div className="h-40 animate-pulse rounded-md bg-muted" />;
  }

  if (quiz.isError) {
    return (
      <Alert>
        <AlertDescription>{apiErrorMessage(quiz.error)}</AlertDescription>
      </Alert>
    );
  }

  const meta = quiz.data;
  if (!meta.is_published || meta.question_count === 0) {
    return (
      <Alert>
        <AlertDescription>
          Bài trắc nghiệm này chưa được mở. Quay lại sau nhé.
        </AlertDescription>
      </Alert>
    );
  }

  const unfinished = history.data?.items.find((row) => row.submitted_at === null);
  const review = attempt?.review ?? null;

  // --- Before starting ----------------------------------------------------

  if (attempt === null) {
    return (
      <section className="space-y-4 rounded-md border p-5">
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="text-lg font-semibold">Bài trắc nghiệm</h2>
          <Badge variant="secondary">
            <ListChecks className="mr-1 size-3.5" />
            {meta.question_count} câu
          </Badge>
          <Badge variant="secondary">
            <Clock className="mr-1 size-3.5" />
            {describeLimit(meta.time_limit_s)}
          </Badge>
          <Badge variant="secondary">Đạt từ {meta.pass_score}%</Badge>
        </div>

        <p className="text-sm text-muted-foreground">
          {meta.time_limit_s === null
            ? "Không tính giờ — cứ làm thong thả."
            : "Đồng hồ chạy ở máy chủ và bắt đầu ngay khi bạn bấm nút. Đóng tab không làm nó dừng lại."}
        </p>

        {begin.isError ? (
          <Alert variant="destructive">
            <AlertDescription>{apiErrorMessage(begin.error)}</AlertDescription>
          </Alert>
        ) : null}

        <Button onClick={() => begin.mutate()} disabled={begin.isPending}>
          {unfinished ? "Tiếp tục làm bài" : "Bắt đầu làm bài"}
        </Button>

        {history.data && history.data.items.length > 0 ? (
          <AttemptHistory rows={history.data.items} />
        ) : null}
      </section>
    );
  }

  // --- The marked paper ---------------------------------------------------

  if (review) {
    return (
      <section className="space-y-4">
        <div
          className={cn(
            "rounded-md border p-5",
            attempt.passed ? "border-emerald-500/40 bg-emerald-500/5" : "border-amber-500/40 bg-amber-500/5",
          )}
        >
          <p className="text-2xl font-semibold">{attempt.score}%</p>
          <p className="text-sm text-muted-foreground">
            {attempt.expired
              ? "Hết giờ trước khi bài được nộp nên lượt này tính 0 điểm."
              : attempt.passed
                ? `Đạt — cần ${attempt.pass_score}% và bạn làm được ${attempt.score}%.`
                : `Chưa đạt — cần ${attempt.pass_score}%. Làm lại được ngay.`}
          </p>
        </div>

        <ol className="space-y-4">
          {review.map((row, index) => (
            <li key={row.id} className="rounded-md border p-4">
              <div className="flex items-start gap-2">
                {row.is_correct ? (
                  <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-emerald-600" />
                ) : (
                  <XCircle className="mt-0.5 size-5 shrink-0 text-destructive" />
                )}
                <p className="font-medium">
                  Câu {index + 1}. {row.question}
                </p>
              </div>

              <ul className="mt-3 space-y-1.5 text-sm">
                {row.options.map((option, optionIndex) => (
                  <li
                    key={optionIndex}
                    className={cn(
                      "rounded-md border px-3 py-2",
                      optionIndex === row.correct_index && "border-emerald-500/50 bg-emerald-500/10",
                      optionIndex === row.your_answer &&
                        optionIndex !== row.correct_index &&
                        "border-destructive/50 bg-destructive/10",
                    )}
                  >
                    {option}
                    {optionIndex === row.correct_index ? (
                      <span className="ml-2 text-xs text-emerald-700">đáp án đúng</span>
                    ) : null}
                    {optionIndex === row.your_answer && optionIndex !== row.correct_index ? (
                      <span className="ml-2 text-xs text-destructive">bạn chọn</span>
                    ) : null}
                  </li>
                ))}
              </ul>

              {row.your_answer === null ? (
                <p className="mt-2 text-sm text-muted-foreground">Bạn chưa trả lời câu này.</p>
              ) : null}

              {row.explanation ? (
                <p className="mt-3 rounded-md bg-muted px-3 py-2 text-sm">{row.explanation}</p>
              ) : null}
            </li>
          ))}
        </ol>

        <Button
          variant="outline"
          onClick={() => {
            setAttempt(null);
            begin.reset();
          }}
        >
          Làm lại
        </Button>
      </section>
    );
  }

  // --- Sitting it ---------------------------------------------------------

  const answered = answers.filter((answer) => answer !== null).length;

  return (
    <section className="space-y-4">
      <div className="sticky top-0 z-10 flex flex-wrap items-center justify-between gap-3 rounded-md border bg-background/95 p-3 backdrop-blur">
        <p className="text-sm text-muted-foreground">
          Đã trả lời {answered}/{attempt.questions.length} câu
        </p>
        {remaining === null ? null : (
          <p
            className={cn(
              "font-mono text-lg tabular-nums",
              remaining <= 30 && "text-destructive",
            )}
            aria-live="polite"
          >
            <Clock className="mr-1 inline size-4" />
            {clock(remaining)}
          </p>
        )}
      </div>

      <ol className="space-y-4">
        {attempt.questions.map((question, index) => (
          <li key={question.id} className="rounded-md border p-4">
            <fieldset>
              <legend className="font-medium">
                Câu {index + 1}. {question.question}
              </legend>
              <div className="mt-3 space-y-1.5">
                {question.options.map((option, optionIndex) => (
                  <label
                    key={optionIndex}
                    className={cn(
                      "flex cursor-pointer items-center gap-3 rounded-md border px-3 py-2 text-sm transition-colors",
                      answers[index] === optionIndex
                        ? "border-primary bg-primary/5"
                        : "hover:bg-muted",
                    )}
                  >
                    <input
                      type="radio"
                      name={question.id}
                      className="size-4"
                      checked={answers[index] === optionIndex}
                      onChange={() =>
                        setAnswers((current) =>
                          current.map((value, position) =>
                            position === index ? optionIndex : value,
                          ),
                        )
                      }
                    />
                    {option}
                  </label>
                ))}
              </div>
            </fieldset>
          </li>
        ))}
      </ol>

      {hand.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(hand.error)}</AlertDescription>
        </Alert>
      ) : null}

      <Button onClick={() => hand.mutate(answers)} disabled={hand.isPending}>
        {hand.isPending ? "Đang nộp..." : "Nộp bài"}
      </Button>
    </section>
  );
}

function AttemptHistory({
  rows,
}: {
  rows: { id: string; submitted_at: string | null; score: number | null; passed: boolean | null }[];
}) {
  const finished = rows.filter((row) => row.submitted_at !== null);
  if (finished.length === 0) return null;

  return (
    <div className="space-y-1 border-t pt-3">
      <p className="text-sm font-medium">Lượt đã làm</p>
      <ul className="space-y-1 text-sm text-muted-foreground">
        {finished.map((row) => (
          <li key={row.id} className="flex items-center gap-2">
            <span>{new Date(row.submitted_at as string).toLocaleString("vi-VN")}</span>
            <span className={cn(row.passed ? "text-emerald-600" : "text-muted-foreground")}>
              {row.score}%{row.passed ? " · đạt" : ""}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
