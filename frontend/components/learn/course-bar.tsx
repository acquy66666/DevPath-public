import { ArrowLeft, Award } from "lucide-react";
import Link from "next/link";

import { CourseCover } from "@/components/courses/course-cover";

/**
 * The strip above every lesson: which course this is, the way back to its
 * page, and how far the reader has got.
 *
 * "x/y bài" is written here and nowhere else on the page -- the contents says
 * "18 bài", the sections "3/3" -- so it is the one number to read, and the
 * golden-flow test finds exactly one.
 *
 * `certificateCode` is for a course finished once and since un-finished (a
 * lesson unticked): the certificate stays, and its link with it. A course
 * that is finished now shows the link in its banner instead, never in both.
 */
export function CourseBar({
  slug,
  courseId,
  title,
  thumbnailUrl,
  completed,
  total,
  certificateCode,
}: {
  slug: string;
  courseId: string;
  title: string;
  thumbnailUrl: string | null;
  completed: number;
  total: number;
  certificateCode: string | null;
}) {
  const percent = total === 0 ? 0 : Math.round((completed / total) * 100);

  return (
    <div className="flex flex-col gap-2.5 border-b pb-4 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between sm:gap-x-6 sm:gap-y-3 sm:pb-5">
      <Link
        href={`/khoa-hoc/${slug}`}
        className="group flex min-w-0 items-center gap-3 rounded-md text-foreground"
      >
        <CourseCover
          thumbnailUrl={thumbnailUrl}
          colorKey={courseId}
          size="xs"
          className="hidden w-16 shrink-0 rounded-sm sm:flex"
        />
        <span className="flex min-w-0 items-center gap-1.5 sm:flex-col sm:items-start sm:gap-0">
          <span className="flex shrink-0 items-center gap-1 text-caption text-muted-foreground">
            <ArrowLeft className="size-4 sm:size-3.5" aria-hidden />
            <span className="sr-only sm:not-sr-only">Về trang khóa học</span>
          </span>
          <span className="truncate text-body-sm font-semibold underline-offset-4 group-hover:underline sm:text-title">
            {title}
          </span>
        </span>
      </Link>

      <div className="flex items-center gap-3">
        <div
          role="progressbar"
          aria-label="Tiến độ khóa học"
          aria-valuemin={0}
          aria-valuemax={total}
          aria-valuenow={completed}
          className="h-2 flex-1 overflow-hidden rounded-full bg-accent sm:w-50 sm:flex-none"
        >
          <div
            className="h-full rounded-full bg-primary transition-[width] duration-progress ease-standard"
            style={{ width: `${percent}%` }}
          />
        </div>
        <p className="shrink-0 text-body-sm font-medium text-muted-foreground tabular-nums">
          {completed}/{total} bài · {percent}%
        </p>
        {certificateCode ? (
          <Link
            href={`/cert/${certificateCode}`}
            className="inline-flex shrink-0 items-center gap-1 text-body-sm font-semibold text-link underline-offset-4 hover:underline"
          >
            <Award className="size-4" aria-hidden />
            Xem chứng chỉ
          </Link>
        ) : null}
      </div>
    </div>
  );
}
