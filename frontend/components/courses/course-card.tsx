import { Star, Users } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { CourseCover } from "@/components/courses/course-cover";
import { Badge } from "@/components/ui/badge";
import { Skeleton, SkeletonRegion, SkeletonText } from "@/components/ui/skeleton";
import type { CourseCard as Course } from "@/lib/api/courses";
import { LEVEL_LABELS } from "@/lib/courses/labels";
import { formatDuration, formatPrice } from "@/lib/format";
import { cn } from "@/lib/utils";

/**
 * One course in the catalogue grid. The whole card is the link.
 *
 * `note` is the line a recommender block adds on top -- why this card is
 * here. Text only: it sits inside the link, and a link cannot hold another.
 */
export function CourseCard({ course, note }: { course: Course; note?: ReactNode }) {
  const duration = formatDuration(course.duration_total_s);
  const rated = course.rating_count > 0;

  return (
    <Link
      href={`/khoa-hoc/${course.slug}`}
      className="group flex h-full flex-col overflow-hidden rounded-lg border transition-colors hover:bg-muted/40 focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
    >
      <CourseCover
        thumbnailUrl={course.thumbnail_url}
        colorKey={course.id}
        iconClassName="size-8"
      />

      <div className="flex flex-1 flex-col gap-2 p-4">
        {note ? (
          <p className="flex items-center gap-1.5 text-xs font-medium text-primary">{note}</p>
        ) : null}

        <div className="flex flex-wrap items-center gap-1.5">
          <Badge variant="secondary">{course.category.name}</Badge>
          <Badge variant="outline">{LEVEL_LABELS[course.level]}</Badge>
        </div>

        <h3 className="line-clamp-2 font-medium group-hover:underline">
          {course.title}
        </h3>

        {course.subtitle ? (
          <p className="line-clamp-2 text-sm text-muted-foreground">
            {course.subtitle}
          </p>
        ) : null}

        <p className="text-sm text-muted-foreground">
          {course.instructor.full_name}
        </p>

        <div className="mt-auto flex flex-wrap items-center gap-x-4 gap-y-1 pt-2 text-xs text-muted-foreground">
          <span className="flex items-center gap-1">
            <Star className="size-3.5" aria-hidden />
            {rated ? `${course.rating_avg} (${course.rating_count})` : "Chưa có đánh giá"}
          </span>
          <span className="flex items-center gap-1">
            <Users className="size-3.5" aria-hidden />
            {course.students_count}
          </span>
          {duration ? <span>{duration}</span> : null}
        </div>

        <p className="pt-1 font-semibold">{formatPrice(course.price)}</p>
      </div>
    </Link>
  );
}

/**
 * A course card on its way: the same frame, cover and rows as `CourseCard`
 * (badges, a one-line title, a two-line subtitle, the instructor, the stats
 * line, the price), so a grid of these is a grid of cards to the pixel when
 * the list lands. `note` for a recommender row, whose cards say why.
 */
export function CourseCardSkeleton({ note = false, className }: { note?: boolean; className?: string }) {
  return (
    <div aria-hidden className={cn("flex h-full flex-col overflow-hidden rounded-lg border", className)}>
      <Skeleton className="aspect-video w-full rounded-none" />
      <div className="flex flex-1 flex-col gap-2 p-4">
        {note ? <SkeletonText size="caption" className="h-4 w-2/3" /> : null}
        <div className="flex gap-1.5">
          <Skeleton className="h-[22px] w-16 rounded-full" />
          <Skeleton className="h-[22px] w-24 rounded-full" />
        </div>
        <SkeletonText className="w-4/5" />
        <div>
          <SkeletonText size="body-sm" />
          <SkeletonText size="body-sm" className="w-2/3" />
        </div>
        <SkeletonText size="body-sm" className="w-1/3" />
        <div className="mt-auto pt-2">
          <SkeletonText size="caption" className="h-4 w-1/2" />
        </div>
        <div className="pt-1">
          <SkeletonText className="w-20" />
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
