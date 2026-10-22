"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { CourseDetailsForm } from "@/components/instructor/course-details-form";
import { CourseStatusBadge } from "@/components/instructor/course-status-badge";
import { CourseStatusCard } from "@/components/instructor/course-status-card";
import { CurriculumBuilder } from "@/components/curriculum/curriculum-builder";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { getCourse } from "@/lib/api/courses";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { useAuth } from "@/lib/auth/auth-provider";

/**
 * One page for one course: what is in it, what it says about itself, and
 * whether it is live.
 *
 * The curriculum comes first because that is the work -- the description and
 * the price are a few minutes at the end, the mục lục is the course.
 */
export function CourseEditor({ courseId }: { courseId: string }) {
  const { accessToken } = useAuth();

  const query = useQuery({
    queryKey: ["course", courseId],
    queryFn: () => getCourse(courseId, accessToken),
    enabled: accessToken !== null,
  });

  if (query.isPending) {
    return (
      <div className="space-y-6">
        <div className="h-9 w-72 animate-pulse rounded-md bg-muted" />
        <div className="h-72 animate-pulse rounded-lg border bg-muted/40" />
        <div className="h-96 animate-pulse rounded-lg border bg-muted/40" />
      </div>
    );
  }

  if (query.isError) {
    return (
      <div className="space-y-4">
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(query.error)}</AlertDescription>
        </Alert>
        <Link
          href="/giang-day"
          className="text-sm text-muted-foreground underline-offset-4 hover:underline"
        >
          ← Về danh sách khóa học
        </Link>
      </div>
    );
  }

  const course = query.data;

  return (
    <div className="space-y-8">
      <div>
        <Link
          href="/giang-day"
          className="text-sm text-muted-foreground underline-offset-4 hover:underline"
        >
          ← Khóa học của tôi
        </Link>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight">{course.title}</h1>
          <CourseStatusBadge status={course.status} />

          {/* Only once published: before that the public page answers 404 to
              everyone the server can identify, which is nobody — it renders
              anonymously. */}
          {course.status === "published" ? (
            <Link
              href={`/khoa-hoc/${course.slug}`}
              className="text-sm text-muted-foreground underline-offset-4 hover:underline"
            >
              Xem trang công khai →
            </Link>
          ) : null}
        </div>
      </div>

      <CurriculumBuilder courseId={course.id} />
      <CourseDetailsForm course={course} />
      <CourseStatusCard course={course} />
    </div>
  );
}
