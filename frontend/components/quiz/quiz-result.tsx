"use client";

import { AlarmClock, ArrowDown, ArrowLeft, BookOpen, Check, Minus, RotateCcw, Star, X } from "lucide-react";
import Link from "next/link";
import { useId, useState, type ReactNode, type Ref } from "react";

import { Mascot, preloadMascot } from "@/components/mascot/mascot";
import { optionLetter, QuizText } from "@/components/quiz/quiz-text";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import type { Attempt, QuestionReview } from "@/lib/api/quiz";
import { formatDateTime } from "@/lib/format";
import {
  LEVEL_CLASSES,
  LEVEL_MOOD,
  QUIZ_LEVELS,
  pointer,
  quizLevel,
  resultCopy,
  rowStatus,
  summarizeReview,
  timeTaken,
  type RowStatus,
} from "@/lib/quiz/result-view";
import { cn } from "@/lib/utils";

/** Start downloading the five result drawings while the paper is being answered. */
export function preloadResultMoods() {
  preloadMascot(...QUIZ_LEVELS.map((level) => LEVEL_MOOD[level]));
}

const STATUS_LABEL: Record<RowStatus, string> = {
  correct: "Đúng",
  wrong: "Sai",
  blank: "Bỏ trống",
  unscored: "Chưa nộp",
};

const STATUS_TONE: Record<RowStatus, { dot: string; text: string }> = {
  correct: { dot: "bg-verdict-ac-solid", text: "text-verdict-ac" },
  wrong: { dot: "bg-verdict-wa-solid", text: "text-verdict-wa" },
  blank: { dot: "bg-input", text: "text-muted-foreground" },
  unscored: { dot: "bg-input", text: "text-muted-foreground" },
};

/**
 * A marked paper: the band in the colour of its level with Naomi, then every
 * question with the key, the student's answer and the explanation.
 *
 * Naomi reacts only to the attempt this page just handed in (`reactTo`); one
 * opened again from the history is a still picture.
 *
 * One primary button per screen. A passed quiz has finished its lesson, so
 * "Bài tiếp theo" under the lesson is the main thing and trying again is an
 * outline. Below half marks with a chapter to go back to, going back is the
 * main thing; otherwise it is trying again.
 */
export function QuizResult({
  attempt,
  number,
  reactTo,
  finished,
  review,
  onRetry,
  retrying,
  retryError,
  onClose,
  bandRef,
}: {
  attempt: Attempt;
  /** "Lượt 2", when the history has counted it. */
  number: number | null;
  reactTo: string | null;
  /** The lesson is ticked, by this quiz or by hand. */
  finished: boolean;
  /** "Ôn lại chương 3": the first lesson of this quiz's chapter. */
  review: { href: string; label: string } | null;
  onRetry: () => void;
  retrying: boolean;
  retryError: string | null;
  /** An attempt reopened from the history can be put away again. */
  onClose: (() => void) | null;
  bandRef?: Ref<HTMLDivElement>;
}) {
  const idPrefix = useId();
  const rows = attempt.review ?? [];
  const score = attempt.score ?? 0;
  const passed = attempt.passed === true;
  const level = quizLevel(score, attempt.expired);
  const tone = LEVEL_CLASSES[level];
  const summary = summarizeReview(rows, attempt.expired);
  const copy = resultCopy({
    score,
    passed,
    expired: attempt.expired,
    passScore: attempt.pass_score,
    correct: summary.correct,
    total: summary.total,
    timeLimitS: attempt.time_limit_s,
  });
  const missedLine = attempt.expired ? null : pointer(summary);
  const missed = [...summary.wrong, ...summary.blank].sort((a, b) => a - b);
  const reacting = reactTo === attempt.id;
  const lessonDone = finished || passed;
  const goBack = !lessonDone && level === "comfort" && review !== null;

  const [onlyMissed, setOnlyMissed] = useState(false);
  // A filter that would hide everything does not apply (and is not offered).
  const filtering = onlyMissed && missed.length > 0;
  const shown = rows
    .map((row, index) => ({ row, number: index + 1 }))
    .filter((entry) => !filtering || missed.includes(entry.number));

  function jumpToMissed() {
    const first = missed[0];
    if (first === undefined) return;
    document.getElementById(`${idPrefix}-r${first}`)?.scrollIntoView({ block: "start" });
  }

  const meta = attempt.submitted_at
    ? attempt.expired
      ? `Hết giờ lúc ${formatDateTime(attempt.submitted_at)}`
      : `Làm trong ${timeTaken(attempt.started_at, attempt.submitted_at)} · nộp lúc ${formatDateTime(attempt.submitted_at)}`
    : null;

  return (
    <section aria-label="Kết quả bài trắc nghiệm" className="flex flex-col gap-4 sm:gap-5">
      <div
        ref={bandRef}
        tabIndex={-1}
        className={cn("flex scroll-mt-6 items-start gap-3.5 rounded-lg p-3.5 outline-none sm:items-center sm:gap-5 sm:p-5", tone.soft)}
      >
        <Mascot mood={LEVEL_MOOD[level]} event={reacting ? attempt.id : null} className="size-20 sm:size-32" />
        <div className="flex min-w-0 flex-1 flex-col gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={cn(
                "inline-flex h-6.5 items-center gap-1.5 rounded-full bg-card px-2.5 text-caption font-semibold",
                tone.text,
              )}
            >
              {level === "party" ? (
                <Star className="size-3.5 fill-reward-mark text-reward-mark" aria-hidden />
              ) : attempt.expired ? (
                <AlarmClock className="size-3.5" aria-hidden />
              ) : passed ? (
                <Check className="size-3.5" strokeWidth={2.5} aria-hidden />
              ) : null}
              {copy.chip}
            </span>
            {number !== null ? (
              <Badge variant="outline" className="bg-card">
                Lượt {number}
                {reacting ? "" : " · xem lại"}
              </Badge>
            ) : null}
          </div>
          <h2 className={cn("flex flex-wrap items-baseline gap-x-3", tone.text)}>
            <span className="text-numeral tabular-nums">{score}%</span>
            <span className="text-title sm:text-h3">{copy.headline}</span>
          </h2>
          <p className="text-body-sm">{copy.hint}</p>
          {missedLine ? (
            <button
              type="button"
              onClick={jumpToMissed}
              className={cn("flex items-start gap-1.5 text-left text-body-sm font-semibold hover:underline", tone.text)}
            >
              <ArrowDown className="mt-0.5 size-4 shrink-0" aria-hidden />
              {missedLine}
            </button>
          ) : null}
          <div aria-hidden className="flex gap-1 pt-1">
            {rows.map((row) => (
              <span key={row.id} className={cn("h-2 flex-1 rounded-full", STATUS_TONE[rowStatus(row, attempt.expired)].dot)} />
            ))}
          </div>
          <div className="flex flex-col gap-2 pt-1 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between sm:gap-x-4">
            {meta ? <p className="text-caption text-muted-foreground tabular-nums">{meta}</p> : null}
            <div className="flex flex-wrap gap-2">
              {goBack && review ? (
                <Link href={review.href} className={buttonVariants({ variant: "default" })}>
                  <BookOpen aria-hidden />
                  {review.label}
                </Link>
              ) : null}
              <Button
                variant={lessonDone || goBack ? "outline" : "default"}
                onClick={onRetry}
                disabled={retrying}
              >
                <RotateCcw aria-hidden />
                {retrying ? "Đang mở bài…" : "Làm lại"}
              </Button>
              {onClose ? (
                <Button variant="outline" onClick={onClose}>
                  <ArrowLeft aria-hidden />
                  Đóng lượt này
                </Button>
              ) : null}
            </div>
          </div>
          {retryError ? (
            <Alert variant="destructive">
              <AlertDescription>{retryError}</AlertDescription>
            </Alert>
          ) : null}
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <h2 className="text-title">Xem lại bài làm</h2>
        {missed.length > 0 ? (
          <div role="group" aria-label="Lọc câu hỏi" className="flex gap-1 rounded-md bg-muted p-1">
            <FilterButton pressed={!filtering} onClick={() => setOnlyMissed(false)}>
              Tất cả · {rows.length}
            </FilterButton>
            <FilterButton pressed={filtering} onClick={() => setOnlyMissed(true)}>
              Câu sai · {missed.length}
            </FilterButton>
          </div>
        ) : null}
      </div>

      <ol className="flex flex-col gap-3">
        {shown.map(({ row, number: questionNumber }) => (
          <ReviewRow
            key={row.id}
            id={`${idPrefix}-r${questionNumber}`}
            row={row}
            number={questionNumber}
            status={rowStatus(row, attempt.expired)}
          />
        ))}
      </ol>
    </section>
  );
}

function FilterButton({
  pressed,
  onClick,
  children,
}: {
  pressed: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      onClick={onClick}
      className={cn(
        "h-8 rounded-sm px-3 text-body-sm font-semibold tabular-nums transition-colors duration-fast",
        pressed ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground",
      )}
    >
      {children}
    </button>
  );
}

function ReviewRow({
  id,
  row,
  number,
  status,
}: {
  id: string;
  row: QuestionReview;
  number: number;
  status: RowStatus;
}) {
  const tone = STATUS_TONE[status];
  return (
    <li id={id} className="flex scroll-mt-6 flex-col gap-3.5 rounded-lg border bg-card p-4 sm:p-5">
      <div className="flex items-center gap-2">
        <span
          aria-hidden
          className={cn("flex size-6 shrink-0 items-center justify-center rounded-full text-primary-foreground", tone.dot)}
        >
          {status === "correct" ? (
            <Check className="size-3.5" strokeWidth={3} />
          ) : status === "wrong" ? (
            <X className="size-3.5" strokeWidth={3} />
          ) : (
            <Minus className="size-3.5" strokeWidth={3} />
          )}
        </span>
        <p className="text-body-sm font-semibold">
          Câu {number} <span className={cn("font-medium", tone.text)}>· {STATUS_LABEL[status]}</span>
        </p>
      </div>
      <h3 className="text-title text-pretty sm:text-body-lg sm:font-semibold">
        <QuizText text={row.question} />
      </h3>
      <ul className="flex flex-col gap-2">
        {row.options.map((option, index) => {
          const key = index === row.correct_index;
          const yours = index === row.your_answer;
          const note = key && yours ? "Bạn chọn · đáp án đúng" : key ? "Đáp án đúng" : yours ? "Bạn chọn" : null;
          return (
            <li
              key={index}
              className={cn(
                "flex min-h-12 flex-wrap items-center gap-x-3 gap-y-1 rounded-md border px-3 py-2.5 sm:px-3.5",
                key
                  ? "border-verdict-ac-solid bg-verdict-ac-soft text-verdict-ac shadow-[inset_0_0_0_1px_var(--color-verdict-ac-solid)]"
                  : yours
                    ? "border-verdict-wa-solid bg-verdict-wa-soft text-verdict-wa shadow-[inset_0_0_0_1px_var(--color-verdict-wa-solid)]"
                    : "border-border text-muted-foreground",
              )}
            >
              <span
                aria-hidden
                className={cn(
                  "flex size-7 shrink-0 items-center justify-center rounded-full text-caption font-semibold",
                  key
                    ? "bg-verdict-ac-solid text-primary-foreground"
                    : yours
                      ? "bg-verdict-wa-solid text-primary-foreground"
                      : "border-[1.5px] border-border-strong",
                )}
              >
                {key ? (
                  <Check className="size-3.5" strokeWidth={3} />
                ) : yours ? (
                  <X className="size-3.5" strokeWidth={3} />
                ) : (
                  optionLetter(index)
                )}
              </span>
              <span className={cn("min-w-0 flex-1 text-body break-words", (key || yours) && "font-medium")}>
                <QuizText text={option} />
              </span>
              {/* Its own line on a phone, under the answer (badge 28 + gap 12
                  = 40 px in): beside it, it squeezed the answer to a word a line. */}
              {note ? <span className="w-full pl-10 text-caption font-semibold sm:w-auto sm:pl-0">{note}</span> : null}
            </li>
          );
        })}
      </ul>
      {row.explanation ? (
        <div className="flex flex-col gap-1 rounded-md bg-muted px-3.5 py-3">
          <p className="text-eyebrow text-muted-foreground uppercase">Giải thích</p>
          <p className="text-body-sm sm:text-body">
            <QuizText text={row.explanation} codeClassName="bg-accent" />
          </p>
        </div>
      ) : null}
    </li>
  );
}
