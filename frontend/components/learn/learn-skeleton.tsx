import { Skeleton, SkeletonText } from "@/components/ui/skeleton";

/**
 * The learning page while its course, progress and contents are on their
 * way: the real frame -- course strip, lesson title, a 16:9 player, the two
 * buttons, the contents card -- so nothing moves when they land.
 */
export function LearnSkeleton() {
  return (
    <div className="flex flex-col gap-6" aria-busy="true">
      <p className="sr-only" role="status">
        Đang tải bài học…
      </p>
      <div className="flex flex-col gap-2.5 border-b pb-4 sm:flex-row sm:items-center sm:justify-between sm:pb-5">
        <div className="flex items-center gap-3">
          <Skeleton className="hidden h-9 w-16 rounded-sm sm:block" />
          <div className="flex flex-col gap-1">
            <SkeletonText size="caption" className="hidden w-28 sm:flex" />
            <SkeletonText size="title" className="w-64 max-w-full" />
          </div>
        </div>
        <SkeletonText size="body-sm" className="w-72 max-w-full" />
      </div>

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_20rem] xl:grid-cols-[minmax(0,1fr)_24rem]">
        <div className="flex min-w-0 flex-col gap-5">
          <div className="flex flex-col gap-2">
            <SkeletonText size="caption" className="w-56" />
            <SkeletonText size="h1" className="w-96 max-w-full" />
            <Skeleton className="h-6.5 w-28 rounded-full" />
          </div>
          <Skeleton className="aspect-video w-full rounded-lg" />
          <div className="flex gap-2">
            <Skeleton className="h-11 w-full sm:h-9 sm:w-52" />
            <Skeleton className="size-11 shrink-0 sm:size-9" />
          </div>
        </div>
        <div className="flex min-w-0 flex-col gap-3">
          <Skeleton className="h-10 w-full" />
          <div className="flex flex-col gap-3.5 rounded-lg border bg-card p-4">
            <SkeletonText size="title" className="w-40" />
            <Skeleton className="h-10 w-full rounded-sm" />
            <SkeletonText size="body-sm" className="w-11/12" />
            <SkeletonText size="body-sm" className="w-3/4" />
            <SkeletonText size="body-sm" className="w-5/6" />
            <Skeleton className="h-10 w-full rounded-sm" />
          </div>
        </div>
      </div>
    </div>
  );
}
