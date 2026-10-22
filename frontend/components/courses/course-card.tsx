import { Star } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { UserAvatar } from "@/components/auth/user-avatar";
import { CourseCover } from "@/components/courses/course-cover";
import { Badge } from "@/components/ui/badge";
import { Skeleton, SkeletonRegion, SkeletonText } from "@/components/ui/skeleton";
import type { CourseCard as Course } from "@/lib/api/courses";
import { LEVEL_LABELS } from "@/lib/courses/labels";
import { formatDuration, formatPrice } from "@/lib/format";
import { cn } from "@/lib/utils";

/** The frame every course card shares, and how it answers the pointer. */
const FRAME =
  "group flex overflow-hidden rounded-lg border bg-card text-card-foreground transition-[box-shadow,translate] duration-fast ease-standard hover:-translate-y-0.5 hover:shadow-md motion-reduce:hover:translate-y-0";

/** "Python · Người mới bắt đầu": one line instead of two badges. */
function eyebrow(course: Course): string {
  return `${course.category.name} · ${LEVEL_LABELS[course.level]}`;
}

/** Comma decimals, as the design system writes numbers: 4,6. */
function rating(course: Course): string {
  return `${Number(course.rating_avg).toLocaleString("vi-VN", { maximumFractionDigits: 1 })} (${course.rating_count})`;
}

function Price({ course }: { course: Course }) {
  return Number(course.price) === 0 ? (
    <Badge variant="success" className="h-6 px-2.5 text-body-sm font-semibold">
      Miễn phí
    </Badge>
  ) : (
    <span className="shrink-0 text-title tabular-nums">{formatPrice(course.price)}</span>
  );
}

/** The stars, or the plain fact that there are none yet. */
function Rating({ course }: { course: Course }) {
  const rated = course.rating_count > 0;

  return (
    <span className="flex min-w-0 items-center gap-1 text-caption text-muted-foreground">
      <Star className={cn("size-3.5 shrink-0", rated && "fill-reward-mark text-reward-mark")} aria-hidden />
      {rated ? (
        <>
          <span className="sr-only">Đánh giá</span>
          {rating(course)}
        </>
      ) : (
        <span className="truncate">Chưa có đánh giá</span>
      )}
    </span>
  );
}

/** Learners and length: "16 học viên · 1 giờ 41 phút". */
function reach(course: Course): string {
  const duration = formatDuration(course.duration_total_s);
  return [`${course.students_count} học viên`, duration].filter(Boolean).join(" · ");
}

/** Why a recommender put the card here. Text only: it sits inside the link. */
function Note({ children }: { children: ReactNode }) {
  return (
    <span className="flex min-w-0 items-center gap-1.5 text-caption font-semibold text-link">
      {children}
    </span>
  );
}

/**
 * One course in a grid. The whole card is the link.
 *
 * `note` is the line a recommender block adds on top -- why this card is
 * here. Text only: it sits inside the link, and a link cannot hold another.
 */
export function CourseCard({ course, note }: { course: Course; note?: ReactNode }) {
  return (
    <Link href={`/khoa-hoc/${course.slug}`} className={cn(FRAME, "h-full flex-col")}>
      <CourseCover thumbnailUrl={course.thumbnail_url} colorKey={course.id} />

      <span className="flex flex-1 flex-col gap-2 p-4">
        {note ? <Note>{note}</Note> : null}

        <span className="line-clamp-1 text-eyebrow text-muted-foreground uppercase">
          {eyebrow(course)}
        </span>

        <span className="line-clamp-2 text-title text-balance group-hover:underline group-hover:underline-offset-4">
          {course.title}
        </span>

        {course.subtitle ? (
          <span className="line-clamp-2 text-body-sm text-muted-foreground">{course.subtitle}</span>
        ) : null}

        <span className="flex min-w-0 items-center gap-2 text-body-sm text-foreground/80">
          <UserAvatar user={course.instructor} className="size-6 text-[0.625rem]" />
          <span className="line-clamp-1">{course.instructor.full_name}</span>
        </span>
        <span className="text-caption text-muted-foreground">{reach(course)}</span>

        <span className="mt-auto flex items-center justify-between gap-3 border-t pt-3">
          <Rating course={course} />
          <Price course={course} />
        </span>
      </span>
    </Link>
  );
}

/**
 * The same course, laid on its side: the cover on the left, the words on the
 * right. For a recommender row that came back with one or two courses -- a
 * four-column grid holding a single card leaves three quarters of the row
 * empty and reads as something that failed to load.
 */
export function CourseRowCard({ course, note }: { course: Course; note?: ReactNode }) {
  return (
    <Link href={`/khoa-hoc/${course.slug}`} className={cn(FRAME, "flex-col sm:flex-row")}>
      <CourseCover
        thumbnailUrl={course.thumbnail_url}
        colorKey={course.id}
        className="sm:aspect-auto sm:w-56 sm:shrink-0"
      />

      <span className="flex min-w-0 flex-1 flex-col gap-1.5 p-4">
        {note ? <Note>{note}</Note> : null}
        <span className="line-clamp-1 text-eyebrow text-muted-foreground uppercase">
          {eyebrow(course)}
        </span>
        <span className="line-clamp-2 text-title text-balance group-hover:underline group-hover:underline-offset-4">
          {course.title}
        </span>
        <span className="line-clamp-1 text-body-sm text-muted-foreground">
          {course.instructor.full_name} · {reach(course)}
        </span>
        <span className="mt-auto flex items-center justify-between gap-3 pt-2">
          <Rating course={course} />
          <Price course={course} />
        </span>
      </span>
    </Link>
  );
}

/**
 * A course card on its way: the same frame, cover and rows as `CourseCard`
 * (the eyebrow, a two-line title, a two-line subtitle, the instructor, the
 * stats and price line), so a grid of these is a grid of cards to the pixel
 * when the list lands. `note` for a recommender row, whose cards say why.
 */
export function CourseCardSkeleton({ note = false, className }: { note?: boolean; className?: string }) {
  return (
    <div aria-hidden className={cn("flex h-full flex-col overflow-hidden rounded-lg border bg-card", className)}>
      <Skeleton className="aspect-video w-full rounded-none" />
      <div className="flex flex-1 flex-col gap-2 p-4">
        {note ? <SkeletonText size="caption" className="w-2/3" /> : null}
        {/* The eyebrow: caption-sized, on its 16px line. */}
        <SkeletonText size="caption" className="h-4 w-1/2" />
        <div>
          <SkeletonText size="title" className="w-full" />
          <SkeletonText size="title" className="w-3/5" />
        </div>
        <div>
          <SkeletonText size="body-sm" />
          <SkeletonText size="body-sm" className="w-2/3" />
        </div>
        <div className="flex items-center gap-2">
          <Skeleton className="size-6 rounded-full" />
          <SkeletonText size="body-sm" className="w-1/3" />
        </div>
        <SkeletonText size="caption" className="w-1/2" />
        <div className="mt-auto flex items-center justify-between gap-3 border-t pt-3">
          <SkeletonText size="caption" className="w-1/3" />
          <Skeleton className="h-6 w-20 rounded-full" />
        </div>
      </div>
    </div>
  );
}

/**
 * A page of course cards on its way (my courses, the wishlist): the count
 * line, then one row of cards -- one on a phone, two from `sm`, three from
 * `lg`, as the grid lays them out -- each with the row of actions those lists
 * put under a card. One row because the length is not known yet, and the
 * first row is what is on screen.
 */
export function CourseListSkeleton({ label }: { label: string }) {
  return (
    <SkeletonRegion label={label} className="space-y-6">
      <SkeletonText className="w-24" />
      <ul className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {[0, 1, 2].map((card) => (
          <li
            key={card}
            className={cn("flex h-full flex-col gap-2", card === 1 && "max-sm:hidden", card === 2 && "max-lg:hidden")}
          >
            <CourseCardSkeleton />
            <div className="flex h-8 items-center justify-between gap-3 px-1">
              <SkeletonText size="caption" className="h-4 w-24" />
              <Skeleton className="h-8 w-28" />
            </div>
          </li>
        ))}
      </ul>
    </SkeletonRegion>
  );
}
