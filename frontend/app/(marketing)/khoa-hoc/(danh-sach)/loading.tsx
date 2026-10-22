import { CourseCardSkeleton } from "@/components/courses/course-card";
import { Skeleton, SkeletonRegion, SkeletonText } from "@/components/ui/skeleton";

/**
 * The catalogue fetches courses and categories on the server, so the browser
 * would otherwise sit on the previous page until both answer. Same heading,
 * same filter grid (search, four selects, the button row), same card grid, so
 * the real page lands where the grey one was instead of shoving it around.
 *
 * It lives in the `(danh-sach)` group, not in `khoa-hoc/` itself, because a
 * `loading.tsx` wraps every segment below it: one level up it also wrapped
 * `khoa-hoc/[slug]`, whose page then streamed before it knew whether the course
 * exists, so an unpublished or mistyped course answered 200 instead of 404.
 */
export default function Loading() {
  return (
    <SkeletonRegion label="Đang tải danh sách khóa học…" className="mx-auto max-w-6xl px-4 py-10">
      <header className="mb-6 space-y-2">
        <SkeletonText size="h1" className="h-9 w-44" />
        <SkeletonText className="w-64" />
      </header>

      <div className="space-y-8">
        <div className="grid grid-cols-2 gap-3 rounded-lg border p-4 lg:grid-cols-[minmax(0,2fr)_repeat(4,minmax(0,1fr))_auto] lg:items-end">
          <Field className="col-span-2 lg:col-span-1" />
          <Field />
          <Field />
          <Field />
          <Field />
          <Skeleton className="col-span-2 h-9 w-24 lg:col-span-1" />
        </div>
        <ul className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2, 3, 4, 5].map((card) => (
            <li key={card} className="h-full">
              <CourseCardSkeleton />
            </li>
          ))}
        </ul>
      </div>
    </SkeletonRegion>
  );
}

/** A label over a control, 6px apart, like FormField. */
function Field({ className }: { className?: string }) {
  return (
    <div className={className}>
      <SkeletonText size="body-sm" className="w-20" />
      <Skeleton className="mt-1.5 h-10 w-full" />
    </div>
  );
}
