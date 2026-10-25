"use client";

import { AlarmClock, CircleCheckBig, Hourglass, ListChecks, Play, RotateCcw } from "lucide-react";
import { useId, type Ref } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import type { Quiz } from "@/lib/api/quiz";
import { formatDateTime } from "@/lib/format";
import { describeLimit, type History } from "@/lib/quiz/result-view";

/**
 * The quiz before an attempt: what it is (questions, time, pass mark), how
 * the clock works, how earlier attempts went, and the button.
 *
 * Opening a lesson must not start a clock, so nothing here starts on mount:
 * the student presses the button. With an attempt still open the button
 * resumes it -- same deadline, the server's clock -- rather than starting a
 * second one.
 *
 * One primary button per screen: once the lesson is done, "Bài tiếp theo"
 * under the lesson is the main thing to do, and trying again is an outline.
 */
export function QuizIntro({
  quiz,
  history,
  finished,
  starting,
  error,
  onStart,
  startRef,
}: {
  quiz: Quiz;
  history: History | null;
  finished: boolean;
  starting: boolean;
  error: string | null;
  onStart: () => void;
  startRef?: Ref<HTMLButtonElement>;
}) {
  const titleId = useId();
  const timed = quiz.time_limit_s !== null;
  const open = history?.open ?? null;
  const tried = (history?.rows.length ?? 0) > 0;
  const facts = `${quiz.question_count} câu · ${
    timed ? describeLimit(quiz.time_limit_s as number) : "không giới hạn thời gian"
  } · đạt từ ${quiz.pass_score}%`;

  return (
    <section aria-labelledby={titleId} className="flex flex-col gap-5 rounded-lg border bg-card p-5 sm:p-6">
      <div className="flex items-center gap-4">
        <span
          aria-hidden
          className="flex size-12 shrink-0 items-center justify-center rounded-lg bg-secondary text-primary"
        >
          <ListChecks className="size-6" />
        </span>
        <div className="flex min-w-0 flex-col gap-0.5">
          <h2 id={titleId} className="text-h3">
            Bài trắc nghiệm
          </h2>
          <p className="text-body-sm text-muted-foreground">
            {tried || open ? facts : "Mỗi câu một đáp án đúng. Kết quả và lời giải thích hiện ngay khi nộp."}
          </p>
        </div>
      </div>

      {tried || open ? null : (
        <dl className="grid grid-cols-3 gap-2 sm:gap-3">
          <Fact term="Số câu" value={`${quiz.question_count} câu`} />
          <Fact term="Thời gian" value={timed ? describeLimit(quiz.time_limit_s as number) : "Không giới hạn"} />
          <Fact term="Điểm đạt" value={`${quiz.pass_score}%`} />
        </dl>
      )}

      {open ? (
        <p className="flex items-start gap-2.5 rounded-md bg-info-soft px-3.5 py-3 text-body-sm text-info-text">
          <AlarmClock className="mt-0.5 size-4.5 shrink-0" aria-hidden />
          <span>
            Bạn đang làm dở một lượt, bắt đầu lúc {formatDateTime(open.started_at)}.
            {timed ? " Đồng hồ vẫn chạy trong lúc bạn rời trang." : null}
          </span>
        </p>
      ) : history?.passed ? (
        <p className="flex items-start gap-2 text-body-sm text-success-text">
          <CircleCheckBig className="mt-0.5 size-4 shrink-0" aria-hidden />
          Bạn đã đạt bài này: cao nhất {history.best}% sau {history.count} lượt.
        </p>
      ) : tried && history?.best !== null ? (
        <p className="text-body-sm text-muted-foreground">
          Điểm cao nhất của bạn: <span className="font-semibold text-foreground tabular-nums">{history?.best}%</span>
        </p>
      ) : null}

      {open ? null : (
        <p className="flex items-start gap-2 text-body-sm text-muted-foreground">
          {timed ? (
            <AlarmClock className="mt-0.5 size-4 shrink-0" aria-hidden />
          ) : (
            <Hourglass className="mt-0.5 size-4 shrink-0" aria-hidden />
          )}
          {timed
            ? "Đồng hồ chạy ở máy chủ và bắt đầu ngay khi bạn bấm nút. Đóng tab không làm nó dừng."
            : "Không tính giờ, cứ làm thong thả."}
        </p>
      )}

      {error ? (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      <div>
        <Button
          ref={startRef}
          size="lg"
          variant={finished && !open ? "outline" : "default"}
          onClick={onStart}
          disabled={starting}
          className="w-full sm:w-auto"
        >
          {open || !tried ? <Play className="fill-current" aria-hidden /> : <RotateCcw aria-hidden />}
          {starting ? "Đang mở bài…" : open ? "Tiếp tục làm bài" : tried ? "Làm lại" : "Bắt đầu làm bài"}
        </Button>
      </div>
    </section>
  );
}

function Fact({ term, value }: { term: string; value: string }) {
  return (
    <div className="min-w-0 rounded-md border bg-background px-3 py-2.5 sm:px-3.5 sm:py-3">
      <dt className="text-caption text-muted-foreground">{term}</dt>
      <dd className="text-title tabular-nums sm:text-h3">{value}</dd>
    </div>
  );
}
