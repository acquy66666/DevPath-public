import { Skeleton, SkeletonRegion, SkeletonText } from "@/components/ui/skeleton";

/**
 * A quiz while it loads: its intro card. Its own file so the learning page
 * can stand it in while the quiz's code is still on its way, without pulling
 * that code into the page's first load.
 */
export function QuizSkeleton() {
  return (
    <SkeletonRegion
      label="Đang tải bài trắc nghiệm"
      className="flex flex-col gap-5 rounded-lg border bg-card p-5 sm:p-6"
    >
      <div className="flex items-center gap-4">
        <Skeleton className="size-12 shrink-0 rounded-lg" />
        <div className="flex w-full max-w-72 flex-col">
          <SkeletonText size="h3" className="w-44" />
          <SkeletonText size="body-sm" />
        </div>
      </div>
      <div className="grid grid-cols-3 gap-2 sm:gap-3">
        <Skeleton className="h-16 sm:h-18" />
        <Skeleton className="h-16 sm:h-18" />
        <Skeleton className="h-16 sm:h-18" />
      </div>
      <Skeleton className="h-11 w-full sm:w-44" />
    </SkeletonRegion>
  );
}
