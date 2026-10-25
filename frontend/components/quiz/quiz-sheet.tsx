"use client";

import { AlarmClock, Check, Hourglass, Info, Loader2, Send } from "lucide-react";
import { useId, type Ref } from "react";

import { optionLetter, QuizText } from "@/components/quiz/quiz-text";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import type { QuestionForAttempt } from "@/lib/api/quiz";
import { formatTimestamp } from "@/lib/format";
import { describeLimit, missingLine } from "@/lib/quiz/result-view";
import { cn } from "@/lib/utils";

/** Under a minute left, the clock turns the colour of running out of time. */
const LOW_S = 60;

/**
 * The paper being answered: a bar that stays on screen (how many answered,
 * a button per question, the clock), the questions, and the hand-in.
 *
 * Every option is a real radio inside its label, so the arrow keys move
 * through a question's options and a screen reader hears "A, 1 trên 4". The
 * clock is a `timer`, silent by design; the workspace's live region speaks
 * at five minutes, one minute and ten seconds instead of every second.
 */
export function QuizSheet({
  questions,
  answers,
  onChoose,
  remaining,
  limit,
  submitting,
  error,
  onSubmit,
  firstRef,
}: {
  questions: QuestionForAttempt[];
  answers: (number | null)[];
  onChoose: (question: number, option: number) => void;
  /** Seconds left on the server's clock, ticking here; null when untimed. */
  remaining: number | null;
  limit: number | null;
  submitting: boolean;
  error: string | null;
  onSubmit: () => void;
  /** The first question, to move focus to when the paper opens. */
  firstRef?: Ref<HTMLFieldSetElement>;
}) {
  const idPrefix = useId();
  const answered = answers.filter((answer) => answer !== null).length;
  const missing = missingLine(answers);
  const low = remaining !== null && remaining <= LOW_S;

  function goTo(index: number) {
    const target = document.getElementById(`${idPrefix}-q${index + 1}`);
    if (!target) return;
    target.scrollIntoView({ block: "start" });
    target.focus({ preventScroll: true });
  }

  return (
    <section aria-label="Bài trắc nghiệm đang làm" className="flex flex-col gap-3 sm:gap-4">
      <div className="sticky top-0 z-10 flex flex-col gap-2.5 rounded-lg border bg-card p-3 shadow-xs sm:flex-row sm:items-center sm:gap-5 sm:py-3.5 sm:pr-4 sm:pl-5">
        <div className="flex min-w-0 flex-1 flex-col gap-2.5">
          <div className="flex items-center justify-between gap-3">
            <p className="text-body-sm font-semibold text-muted-foreground">
              Đã trả lời{" "}
              <span className="text-foreground tabular-nums">
                {answered}/{questions.length}
              </span>{" "}
              câu
            </p>
            {/* Phones: the clock shares the first row. */}
            <Clock remaining={remaining} limit={limit} low={low} compact className="sm:hidden" />
          </div>
          <nav aria-label="Đi tới câu hỏi" className="flex flex-wrap gap-1.5">
            {questions.map((question, index) => {
              const done = answers[index] !== null;
              return (
                <button
                  key={question.id}
                  type="button"
                  onClick={() => goTo(index)}
                  aria-label={`Câu ${index + 1}, ${done ? "đã trả lời" : "chưa trả lời"}`}
                  className={cn(
                    "flex h-9 min-w-9 items-center justify-center rounded-sm px-2 text-body-sm font-semibold tabular-nums transition-colors duration-fast sm:h-8 sm:min-w-8",
                    done
                      ? "bg-primary text-primary-foreground hover:bg-primary-hover"
                      : "border border-input bg-card text-muted-foreground hover:bg-accent",
                  )}
                >
                  {index + 1}
                </button>
              );
            })}
          </nav>
        </div>
        <Clock remaining={remaining} limit={limit} low={low} className="hidden sm:flex" />
      </div>

      <ol className="flex flex-col gap-3 sm:gap-4">
        {questions.map((question, index) => {
          const chosen = answers[index];
          const legendId = `${idPrefix}-q${index + 1}-text`;
          return (
            <li key={question.id}>
              <fieldset
                id={`${idPrefix}-q${index + 1}`}
                ref={index === 0 ? firstRef : undefined}
                tabIndex={-1}
                aria-labelledby={legendId}
                className="flex min-w-0 scroll-mt-40 flex-col gap-3.5 rounded-lg border bg-card p-4 outline-none sm:p-5"
              >
                <div className="flex items-center justify-between gap-3">
                  <p className="text-eyebrow text-link uppercase tabular-nums">
                    Câu {index + 1} / {questions.length}
                  </p>
                  <p className="flex items-center gap-1 text-caption text-muted-foreground">
                    {chosen !== null ? <Check className="size-3.5" strokeWidth={2.5} aria-hidden /> : null}
                    {chosen !== null ? "Đã trả lời" : "Chưa trả lời"}
                  </p>
                </div>
                <p id={legendId} className="text-title text-pretty sm:text-body-lg sm:font-semibold">
                  <QuizText text={question.question} />
                </p>
                <div className="flex flex-col gap-2">
                  {question.options.map((option, optionIndex) => {
                    const picked = chosen === optionIndex;
                    return (
                      <label
                        key={optionIndex}
                        className={cn(
                          "relative flex min-h-13 cursor-pointer items-center gap-3 rounded-md border px-3 py-2.5 transition-colors duration-fast sm:px-3.5",
                          "has-[input:focus-visible]:outline-2 has-[input:focus-visible]:outline-offset-2 has-[input:focus-visible]:outline-ring",
                          picked
                            ? "border-primary bg-secondary shadow-[inset_0_0_0_1px_var(--color-primary)]"
                            : "border-border-strong bg-card hover:border-input hover:bg-background",
                        )}
                      >
                        <input
                          type="radio"
                          name={`${idPrefix}-q${index + 1}`}
                          className="sr-only"
                          checked={picked}
                          onChange={() => onChoose(index, optionIndex)}
                        />
                        <span
                          aria-hidden
                          className={cn(
                            "flex size-7 shrink-0 items-center justify-center rounded-full border-[1.5px] text-caption font-semibold",
                            picked
                              ? "border-primary bg-primary text-primary-foreground"
                              : "border-input text-muted-foreground",
                          )}
                        >
                          {optionLetter(optionIndex)}
                        </span>
                        <span
                          className={cn(
                            "min-w-0 text-body break-words",
                            picked && "font-medium text-secondary-foreground",
                          )}
                        >
                          <QuizText text={option} />
                        </span>
                      </label>
                    );
                  })}
                </div>
              </fieldset>
            </li>
          );
        })}
      </ol>

      <div className="flex flex-col gap-3 rounded-lg border bg-card p-4 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between sm:gap-x-5 sm:py-4 sm:pr-4 sm:pl-5">
        <div className="flex min-w-0 flex-col gap-0.5 sm:flex-[1_1_18rem]">
          <p className="text-title">{missing.title}</p>
          <p className="text-body-sm text-muted-foreground">
            {missing.complete
              ? "Nộp khi bạn đã sẵn sàng. Nộp rồi thì không sửa được nữa."
              : "Câu bỏ trống tính là sai. Nộp rồi thì không sửa được nữa."}
          </p>
        </div>
        <Button size="lg" onClick={onSubmit} disabled={submitting} className="w-full sm:w-auto">
          {submitting ? <Loader2 className="animate-spin" aria-hidden /> : <Send aria-hidden />}
          {submitting ? "Đang nộp…" : "Nộp bài"}
        </Button>
        {error ? (
          <Alert variant="destructive" className="sm:basis-full">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : null}
      </div>
      {limit !== null ? (
        <p className="flex items-start gap-1.5 text-caption text-muted-foreground">
          <Info className="mt-px size-3.5 shrink-0" aria-hidden />
          Đồng hồ chạy ở máy chủ: đóng tab không làm nó dừng. Hết giờ thì bài được nộp với những câu đã chọn.
        </p>
      ) : null}
    </section>
  );
}

function Clock({
  remaining,
  limit,
  low,
  compact = false,
  className,
}: {
  remaining: number | null;
  limit: number | null;
  low: boolean;
  compact?: boolean;
  className?: string;
}) {
  if (remaining === null || limit === null) {
    return (
      <p className={cn("shrink-0 items-center gap-1.5 text-body-sm font-medium text-muted-foreground", compact ? "flex" : "", className)}>
        <Hourglass className="size-4" aria-hidden />
        Không tính giờ
      </p>
    );
  }

  if (compact) {
    return (
      <p
        role="timer"
        aria-label="Thời gian còn lại"
        className={cn(
          "flex h-8 shrink-0 items-center gap-1.5 rounded-full px-2.5 text-lg font-semibold tabular-nums",
          low ? "bg-verdict-tle-soft text-verdict-tle" : "bg-muted text-foreground",
          className,
        )}
      >
        <AlarmClock className={cn("size-4", !low && "text-muted-foreground")} aria-hidden />
        {formatTimestamp(remaining)}
      </p>
    );
  }

  return (
    <div
      className={cn(
        "shrink-0 flex-col items-end gap-0.5 rounded-md px-3.5 py-2",
        low ? "bg-verdict-tle-soft text-verdict-tle" : "bg-muted",
        className,
      )}
    >
      <p role="timer" aria-label="Thời gian còn lại" className="flex items-center gap-2 text-numeral tabular-nums">
        <AlarmClock className={cn("size-5", !low && "text-muted-foreground")} aria-hidden />
        {formatTimestamp(remaining)}
      </p>
      <p className={cn("text-caption", low ? "font-semibold" : "text-muted-foreground")}>
        {low ? "Còn dưới 1 phút" : `còn lại trong ${describeLimit(limit)}`}
      </p>
    </div>
  );
}
