import { CourseCardSkeleton } from "@/components/courses/course-card";
import { Skeleton, SkeletonRegion, SkeletonText } from "@/components/ui/skeleton";

/**
 * The catalogue fetches courses and categories on the server, so the browser
 * would otherwise sit on the previous page until both answer. Same head on
 * `card` (title, search box, topic pills), same result line, same card grid,
 * so the real page lands where the grey one was instead of shoving it around.
 *
 * It lives in the `(danh-sach)` group, not in `khoa-hoc/` itself, because a
 * `loading.tsx` wraps every segment below it: one level up it also wrapped
 * `khoa-hoc/[slug]`, whose page then streamed before it knew whether the course
 * exists, so an unpublished or mistyped course answered 200 instead of 404.
 */
export default function Loading() {
  return (
    <SkeletonRegion label="Đang tải danh sách khóa học…">
      <div className="border-b bg-card">
        <div className="mx-auto max-w-6xl space-y-5 px-4 pt-10 pb-6">
          <div className="space-y-1.5">
            <SkeletonText size="h1" className="w-40" />
            <SkeletonText className="w-[min(26rem,100%)]" />
          </div>
          <div className="flex max-w-3xl gap-2">
            <Skeleton className="h-12 flex-1" />
            <Skeleton className="h-12 w-20" />
          </div>
          <div className="flex flex-wrap gap-2">
            {[18, 30, 21, 21, 38, 18, 26, 37, 58].map((width, index) => (
              <Skeleton key={index} className="h-9 rounded-full" style={{ width: `${width * 4}px` }} />
            ))}
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-6xl space-y-6 px-4 pt-6 pb-16">
        <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
          <SkeletonText className="w-32" />
          {/* The "Bộ lọc" button on a phone, three selects from md. */}
          <Skeleton className="h-9 w-28 md:hidden" />
          <div className="hidden gap-3 md:flex">
            {[0, 1, 2].map((field) => (
              <div key={field} className="w-44 space-y-1.5">
                <SkeletonText size="body-sm" className="w-16" />
                <Skeleton className="h-10 w-full" />
              </div>
            ))}
          </div>
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
