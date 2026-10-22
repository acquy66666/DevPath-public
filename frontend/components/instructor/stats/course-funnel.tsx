"use client";

import { useQuery } from "@tanstack/react-query";
import { BookOpen, Code2, FileQuestion, PlayCircle } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ExportButton } from "@/components/ui/export-button";
import { apiErrorMessage } from "@/lib/api/error-messages";
import {
  funnelExportPath,
  getCourseFunnel,
  type LessonStats,
  type StatsCourse,
} from "@/lib/api/instructor-stats";

import { formatCount, formatRate } from "./format";

const ICONS = {
  video: PlayCircle,
  article: BookOpen,
  quiz: FileQuestion,
  code_exercise: Code2,
} as const;

const TYPE_LABELS = {
  video: "Video",
  article: "Bài đọc",
  quiz: "Quiz",
  code_exercise: "Bài code",
} as const;

/**
 * Where the learners of one course stop: every lesson in order, with the
 * share of enrolments that finished it drawn as a bar. The deepest drop from
 * one lesson to the next is marked -- that is the lesson to look at first.
 */
export function CourseFunnelDialog({
  accessToken,
  course,
  onClose,
}: {
  accessToken: string;
  course: StatsCourse | null;
  onClose: () => void;
}) {
  const query = useQuery({
    queryKey: ["instructor-stats", "funnel", course?.id],
    queryFn: () => getCourseFunnel(accessToken, course!.id),
    enabled: course !== null,
  });

  const lessons = query.data?.lessons ?? [];
  const drop = deepestDrop(lessons);

  return (
    <Dialog open={course !== null} onOpenChange={(open) => (open ? null : onClose())}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>Học viên dừng ở đâu</DialogTitle>
          <DialogDescription>
            {course?.title}
            {query.data ? ` · ${formatCount(query.data.enrollments)} lượt ghi danh` : null}. Lượt đã
            hoàn thành khóa được tính là đã xong mọi bài.
          </DialogDescription>
        </DialogHeader>

        {course ? (
          <div className="flex justify-end">
            <ExportButton path={funnelExportPath(course.id)} filename="devpath_bai-hoc.xlsx" />
          </div>
        ) : null}

        {query.isPending ? (
          <div className="h-48 animate-pulse rounded-md bg-muted/40" />
        ) : query.isError ? (
          <Alert variant="destructive">
            <AlertDescription>{apiErrorMessage(query.error)}</AlertDescription>
          </Alert>
        ) : lessons.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            Khóa học này chưa có bài học nào.
          </p>
        ) : (
          <ol className="space-y-2">
            {lessons.map((lesson, index) => {
              const Icon = ICONS[lesson.type];
              const firstOfSection =
                index === 0 || lessons[index - 1].section_title !== lesson.section_title;
              return (
                <li key={lesson.lesson_id}>
                  {firstOfSection ? (
                    <p className="mt-3 mb-1 text-xs font-medium tracking-wide text-muted-foreground uppercase">
                      {lesson.section_title}
                    </p>
                  ) : null}
                  <div
                    className={
                      drop === index
                        ? "rounded-md border border-amber-500/60 bg-amber-50 p-3 dark:bg-amber-950/30"
                        : "rounded-md border p-3"
                    }
                  >
                    <div className="flex items-start justify-between gap-3">
                      <p className="flex min-w-0 items-center gap-2 text-sm font-medium">
                        <Icon className="size-4 shrink-0 text-muted-foreground" aria-hidden />
                        <span className="truncate">{lesson.title}</span>
                        <span className="sr-only">({TYPE_LABELS[lesson.type]})</span>
                      </p>
                      <span className="shrink-0 text-sm tabular-nums">
                        {formatRate(lesson.completion_rate)}
                      </span>
                    </div>
                    <div
                      role="meter"
                      aria-label={`Hoàn thành bài ${lesson.title}`}
                      aria-valuemin={0}
                      aria-valuemax={100}
                      aria-valuenow={
                        lesson.completion_rate === null
                          ? undefined
                          : Math.round(lesson.completion_rate * 100)
                      }
                      className="mt-2 h-2 overflow-hidden rounded-full bg-primary/15"
                    >
                      <div
                        className="h-full rounded-full bg-primary"
                        style={{ width: `${(lesson.completion_rate ?? 0) * 100}%` }}
                      />
                    </div>
                    <p className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
                      <span>{formatCount(lesson.started)} đã mở</span>
                      <span>{formatCount(lesson.completed)} đã xong</span>
                      {lesson.avg_watched !== null ? (
                        <span>xem trung bình {formatRate(lesson.avg_watched)} video</span>
                      ) : null}
                      {lesson.quiz_first_try_pass_rate !== null ? (
                        <span>đạt lần đầu {formatRate(lesson.quiz_first_try_pass_rate)}</span>
                      ) : null}
                      {lesson.code_solve_rate !== null ? (
                        <span>giải được {formatRate(lesson.code_solve_rate)}</span>
                      ) : null}
                      {lesson.questions > 0 ? <span>{formatCount(lesson.questions)} câu hỏi</span> : null}
                      {lesson.notes > 0 ? <span>{formatCount(lesson.notes)} ghi chú</span> : null}
                    </p>
                    {drop === index ? (
                      <p className="mt-1 text-xs font-medium text-amber-800 dark:text-amber-300">
                        Rơi nhiều nhất so với bài trước — nên xem lại bài này.
                      </p>
                    ) : null}
                  </div>
                </li>
              );
            })}
          </ol>
        )}
      </DialogContent>
    </Dialog>
  );
}

/** Index of the lesson with the biggest fall in completion from the one before. */
function deepestDrop(lessons: LessonStats[]): number | null {
  let best: number | null = null;
  let deepest = 0.05; // smaller falls are noise, not a finding
  for (let index = 1; index < lessons.length; index += 1) {
    const before = lessons[index - 1].completion_rate;
    const now = lessons[index].completion_rate;
    if (before === null || now === null) continue;
    if (before - now > deepest) {
      deepest = before - now;
      best = index;
    }
  }
  return best;
}
