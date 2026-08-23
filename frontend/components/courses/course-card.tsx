import { GraduationCap, Star, Users } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import type { CourseCard as Course } from "@/lib/api/courses";
import { LEVEL_LABELS } from "@/lib/courses/labels";
import { formatDuration, formatPrice } from "@/lib/format";

/** One course in the catalogue grid. The whole card is the link. */
export function CourseCard({ course }: { course: Course }) {
  const duration = formatDuration(course.duration_total_s);
  const rated = course.rating_count > 0;

  return (
    <Link
      href={`/khoa-hoc/${course.slug}`}
      className="group flex h-full flex-col overflow-hidden rounded-xl border transition-colors hover:bg-muted/40 focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
    >
      {course.thumbnail_url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={course.thumbnail_url}
          alt=""
          className="aspect-video w-full bg-muted object-cover"
        />
      ) : (
        <div className="flex aspect-video w-full items-center justify-center bg-muted">
          <GraduationCap className="size-8 text-muted-foreground" aria-hidden />
        </div>
      )}

      <div className="flex flex-1 flex-col gap-2 p-4">
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
