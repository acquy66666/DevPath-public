import { Skeleton, SkeletonRegion, SkeletonText } from "@/components/ui/skeleton";

/**
 * The sign-in card on its way: title and line, two fields (label over a
 * 40px input), the button and the line under it -- 338px, as the real card.
 * The sign-up card has one field more and simply grows when it lands.
 */
export default function AuthLoading() {
  return (
    <SkeletonRegion label="Đang mở biểu mẫu…">
      <div className="flex flex-col gap-4 rounded-lg border bg-card py-4">
        <div className="grid gap-1 px-4">
          <SkeletonText size="h3" className="w-32" />
          <SkeletonText size="body-sm" className="w-56" />
        </div>
        <div className="space-y-4 px-4">
          {[0, 1].map((field) => (
            <div key={field}>
              <SkeletonText size="body-sm" className="w-20" />
              <Skeleton className="mt-1.5 h-10 w-full" />
            </div>
          ))}
          <Skeleton className="h-9 w-full" />
          <SkeletonText size="body-sm" className="mx-auto w-48" />
        </div>
      </div>
    </SkeletonRegion>
  );
}
