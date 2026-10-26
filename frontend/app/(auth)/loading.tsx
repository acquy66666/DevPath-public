import { Skeleton, SkeletonRegion, SkeletonText } from "@/components/ui/skeleton";

/**
 * The sign-in card on its way, in the frame of `AuthShell`: on a wide screen
 * the green side panel and the form beside it (1040 × 558 px), on a phone the
 * form alone (446 px at 375). Measured 27/10 on the sign-in card; the sign-up
 * card has one field more and simply grows when it lands.
 */
export default function AuthLoading() {
  return (
    <SkeletonRegion label="Đang mở biểu mẫu…" className="w-full max-w-md lg:max-w-[65rem]">
      <div className="h-[446px] overflow-hidden rounded-xl border bg-card shadow-md lg:grid lg:h-[558px] lg:grid-cols-[minmax(0,1fr)_minmax(0,27.5rem)]">
        <div className="hidden bg-secondary lg:block" />
        <div className="flex flex-col gap-5 px-5 py-6 sm:px-6 lg:p-10">
          <div className="flex items-center gap-3">
            <Skeleton className="size-18 rounded-lg lg:hidden" />
            <SkeletonText size="h2" className="w-36" />
          </div>
          <SkeletonText size="body" className="w-64 max-w-full" />
          {[0, 1].map((field) => (
            <div key={field}>
              <SkeletonText size="body-sm" className="w-20" />
              <Skeleton className="mt-1.5 h-10 w-full" />
            </div>
          ))}
          <Skeleton className="h-11 w-full" />
          <SkeletonText size="body-sm" className="mx-auto w-48" />
        </div>
      </div>
    </SkeletonRegion>
  );
}
