import type { ReactNode } from "react";

import { Skeleton, SkeletonRegion, SkeletonText } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

/**
 * One skeleton per instructor screen, used three times over so nothing moves
 * between them: by the route's `loading.tsx` while the server answers, by
 * `InstructorGate` while the session is restored, and by the screen itself
 * while its first query is in flight. Each one carries its page's container
 * and draws the page's own frame -- heading, toolbar, a typical number of
 * rows -- so the layout shift when the data lands is only what the data
 * itself adds (measured on 22/10, `docs/report/assets/phase-7/site-states.md`).
 */
function Frame({ width, label, children }: { width: string; label: string; children: ReactNode }) {
  return (
    <SkeletonRegion label={label} className={cn("mx-auto space-y-6 px-4 py-12", width)}>
      {children}
    </SkeletonRegion>
  );
}

/** Back link, title, one line of description: the head of most screens. */
function Heading({ back = true, lines = 1 }: { back?: boolean; lines?: 1 | 2 }) {
  return (
    <div>
      {back ? <SkeletonText size="body-sm" className="mb-2 w-36" /> : null}
      <SkeletonText size="h2" className="w-64 max-w-full" />
      <SkeletonText size="body-sm" className="w-full max-w-md" />
      {lines === 2 ? <SkeletonText size="body-sm" className="w-2/3 max-w-sm" /> : null}
    </div>
  );
}

/** A row of the course list, the Q&A inbox: bordered, title, a line, a meta line. */
function RowSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn("space-y-1.5 rounded-lg border p-4", className)}>
      <SkeletonText className="w-2/3" />
      <SkeletonText size="body-sm" className="w-1/2" />
      <SkeletonText size="caption" className="h-4 w-48" />
    </div>
  );
}

/** `/giang-day`: the course list. */
export function TeachingSkeleton() {
  return (
    <Frame width="max-w-4xl" label="Đang tải khóa học của bạn…">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <Heading back={false} lines={2} />
        <div className="flex flex-wrap gap-2 sm:max-w-80 sm:justify-end">
          <Skeleton className="h-9 w-28" />
          <Skeleton className="h-9 w-28" />
          <Skeleton className="h-9 w-28" />
          <Skeleton className="h-9 w-36" />
        </div>
      </div>
      <TeachingRowsSkeleton />
    </Frame>
  );
}

/** The rows alone, for the list while its query is in flight. */
export function TeachingRowsSkeleton() {
  return (
    <div className="space-y-3" aria-hidden>
      {[0, 1, 2].map((row) => (
        <RowSkeleton key={row} />
      ))}
    </div>
  );
}

/** `/giang-day/hoi-dap`: the inbox. */
export function QaInboxSkeleton() {
  return (
    <Frame width="max-w-[50rem]" label="Đang tải hỏi đáp…">
      <Heading lines={2} />
      <div className="flex flex-wrap items-center gap-4">
        <Skeleton className="h-10 w-64" />
        <SkeletonText size="body-sm" className="w-40" />
      </div>
      <QaRowsSkeleton />
    </Frame>
  );
}

/** The inbox's rows alone. */
export function QaRowsSkeleton() {
  return (
    <div className="space-y-3" aria-hidden>
      {[0, 1, 2].map((row) => (
        <RowSkeleton key={row} className="rounded-md p-3" />
      ))}
    </div>
  );
}

/** `/giang-day/thong-ke`: heading, tier line, eight tiles, the chart. */
export function StatsSkeleton() {
  return (
    <Frame width="max-w-6xl" label="Đang tải thống kê…">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <Heading />
        <div className="flex flex-wrap items-center gap-2">
          <Skeleton className="h-9 w-72" />
          <Skeleton className="h-9 w-28" />
        </div>
      </div>
      <TierLineSkeleton />
      <StatsBodySkeleton />
    </Frame>
  );
}

/** The tier line above the numbers: icon, two lines, progress on the right. */
export function TierLineSkeleton() {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border bg-card p-4" aria-hidden>
      <div className="flex items-center gap-3">
        <Skeleton className="size-10" />
        <div>
          <SkeletonText size="body-sm" className="w-28" />
          <SkeletonText className="w-56" />
        </div>
      </div>
      <SkeletonText size="body-sm" className="w-52" />
    </div>
  );
}

/** Eight tiles and the chart card: what the stats page shows before its first answer. */
export function StatsBodySkeleton() {
  return (
    <div className="space-y-6" aria-hidden>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[0, 1, 2, 3, 4, 5, 6, 7].map((tile) => (
          <div key={tile} className="rounded-lg border bg-card p-4">
            <SkeletonText size="body-sm" className="w-32" />
            <SkeletonText size="h2" className="mt-1 w-20" />
            <SkeletonText size="caption" className="mt-1 h-4 w-40" />
          </div>
        ))}
      </div>
      <Skeleton className="h-80 rounded-lg" />
    </div>
  );
}

/** `/giang-day/cap-bac`: heading, the current tier card, the ladder. */
export function TierSkeleton() {
  return (
    <Frame width="max-w-4xl" label="Đang tải cấp giảng viên…">
      <Heading lines={2} />
      <TierBodySkeleton />
    </Frame>
  );
}

/**
 * The tier cards alone. The real page (current tier, the whole ladder, the
 * history) is always longer than a screen, so this reserves one.
 */
export function TierBodySkeleton() {
  return (
    <div className="min-h-[75dvh] space-y-6" aria-hidden>
      <div className="rounded-lg border bg-card p-4">
        <div className="flex items-center gap-4">
          <Skeleton className="size-12 rounded-lg" />
          <div>
            <SkeletonText size="body-sm" className="w-24" />
            <SkeletonText size="h3" className="w-64 max-w-full" />
          </div>
        </div>
      </div>
      <Skeleton className="h-96 rounded-lg" />
    </div>
  );
}

/** `/giang-day/[courseId]`: back link, title and badge, the details form, the curriculum. */
export function CourseEditorSkeleton() {
  return (
    <Frame width="max-w-4xl" label="Đang tải khóa học…">
      <CourseEditorBodySkeleton />
    </Frame>
  );
}

/** The editor alone, inside the page's own container. */
export function CourseEditorBodySkeleton() {
  return (
    <div className="space-y-8" aria-hidden>
      <div>
        <SkeletonText size="body-sm" className="w-36" />
        <div className="mt-4 flex items-center gap-3">
          <SkeletonText size="h2" className="w-80 max-w-full" />
          <Skeleton className="h-[22px] w-20 rounded-full" />
        </div>
      </div>
      <Skeleton className="h-[30rem] rounded-lg" />
      <Skeleton className="h-96 rounded-lg" />
    </div>
  );
}

/** The skeleton of the instructor screen at `pathname`, for the gate. */
export function instructorSkeletonFor(pathname: string): ReactNode {
  if (pathname === "/giang-day") return <TeachingSkeleton />;
  if (pathname.startsWith("/giang-day/thong-ke")) return <StatsSkeleton />;
  if (pathname.startsWith("/giang-day/hoi-dap")) return <QaInboxSkeleton />;
  if (pathname.startsWith("/giang-day/cap-bac")) return <TierSkeleton />;
  if (pathname.startsWith("/giang-day/moi")) {
    return (
      <Frame width="max-w-2xl" label="Đang mở biểu mẫu…">
        <Heading />
        <Skeleton className="h-[28rem] rounded-lg" />
      </Frame>
    );
  }
  return <CourseEditorSkeleton />;
}
