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
    <SkeletonRegion label={label} className={cn("mx-auto space-y-6 px-4 py-6 sm:py-8", width)}>
      {children}
    </SkeletonRegion>
  );
}

/** Title and one or two lines of description: the head of most screens. */
function Heading({ lines = 1 }: { lines?: 1 | 2 }) {
  return (
    <div className="space-y-1.5">
      <SkeletonText size="h1" className="w-64 max-w-full" />
      <SkeletonText className="w-full max-w-md" />
      {lines === 2 ? <SkeletonText className="w-2/3 max-w-sm" /> : null}
    </div>
  );
}

/** The bar of places under the header, while the session is restored. */
export function InstructorNavSkeleton() {
  return (
    <div className="border-b bg-card" aria-hidden>
      <div className="mx-auto flex h-12 max-w-6xl items-center gap-6 px-4 md:h-13">
        <SkeletonText size="caption" className="hidden w-20 md:flex" />
        <div className="flex flex-1 gap-6">
          <SkeletonText size="body-sm" className="w-16" />
          <SkeletonText size="body-sm" className="w-14" />
          <SkeletonText size="body-sm" className="w-16" />
          <SkeletonText size="body-sm" className="w-14" />
        </div>
        <Skeleton className="hidden h-9 w-36 sm:block" />
      </div>
    </div>
  );
}

/** `/giang-day`: the overview. */
export function TeachingSkeleton() {
  return (
    <Frame width="max-w-6xl" label="Đang tải khóa học của bạn…">
      <OverviewBodySkeleton />
    </Frame>
  );
}

/** The overview inside its page: greeting, waiting tasks, the course rows. */
export function OverviewBodySkeleton() {
  return (
    <div className="space-y-8" aria-hidden>
      <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_26rem] lg:gap-6">
        <div className="flex items-center gap-4 rounded-xl bg-secondary p-5 sm:gap-6 sm:px-8 sm:py-7">
          <Skeleton className="size-18 rounded-full bg-card sm:size-28" />
          <div className="flex-1 space-y-1.5">
            <SkeletonText size="h1" className="w-48" />
            <SkeletonText className="w-full max-w-sm" />
          </div>
        </div>
        <div className="space-y-3 rounded-lg border bg-card p-4 sm:p-5">
          <SkeletonText size="title" className="w-32" />
          {[0, 1, 2].map((row) => (
            <div key={row} className="flex items-center gap-3">
              <Skeleton className="size-8" />
              <SkeletonText size="body-sm" className="flex-1" />
            </div>
          ))}
        </div>
      </div>
      <Skeleton className="h-11 sm:hidden" />
      <div className="space-y-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <SkeletonText size="h3" className="w-48" />
          <div className="flex gap-1.5">
            <Skeleton className="h-8 w-24 rounded-full" />
            <Skeleton className="h-8 w-32 rounded-full" />
            <Skeleton className="h-8 w-24 rounded-full" />
          </div>
        </div>
        <div className="divide-y rounded-xl border bg-card">
          {[0, 1, 2, 3].map((row) => (
            <div
              key={row}
              className="grid grid-cols-[5rem_minmax(0,1fr)] items-center gap-3 p-3 sm:grid-cols-[8rem_minmax(0,1fr)_6rem] sm:gap-5 sm:px-5 sm:py-3.5"
            >
              <Skeleton className="aspect-video w-full rounded-md" />
              <div className="space-y-1.5">
                <SkeletonText size="title" className="w-2/3" />
                <SkeletonText size="caption" className="w-1/2" />
              </div>
              <Skeleton className="hidden h-[22px] w-24 rounded-full sm:block" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/** `/giang-day/hoi-dap`: the inbox. */
export function QaInboxSkeleton() {
  return (
    <Frame width="max-w-[50rem]" label="Đang tải hỏi đáp…">
      <Heading />
      <div className="flex flex-col gap-3 border-b sm:flex-row sm:items-end sm:justify-between">
        <div className="order-last flex h-10 items-center gap-4 sm:order-none">
          <SkeletonText size="body-sm" className="w-32" />
          <SkeletonText size="body-sm" className="w-12" />
        </div>
        <Skeleton className="h-10 w-full sm:mb-2 sm:w-64" />
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
        <div key={row} className="flex gap-4 rounded-lg border bg-card p-4">
          <Skeleton className="h-16 w-12" />
          <div className="flex-1 space-y-1.5">
            <SkeletonText size="caption" className="w-1/2" />
            <SkeletonText size="title" className="w-2/3" />
            <SkeletonText size="body-sm" className="w-full" />
            <SkeletonText size="caption" className="w-40" />
          </div>
        </div>
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

/** `/giang-day/[courseId]`: breadcrumb, title, tabs, the curriculum and its side cards. */
export function CourseEditorSkeleton() {
  return (
    <Frame width="max-w-6xl" label="Đang tải khóa học…">
      <CourseEditorBodySkeleton />
    </Frame>
  );
}

/** The editor alone, inside the page's own container. */
export function CourseEditorBodySkeleton() {
  return (
    <div className="space-y-5" aria-hidden>
      <div className="space-y-2.5">
        <SkeletonText size="body-sm" className="w-56" />
        <div className="flex items-center gap-3">
          <SkeletonText size="h1" className="w-96 max-w-full" />
          <Skeleton className="h-[22px] w-24 rounded-full" />
        </div>
      </div>
      <div className="flex h-10 items-center gap-4 shadow-[inset_0_-1px_0_var(--color-border)]">
        <SkeletonText size="body-sm" className="w-20" />
        <SkeletonText size="body-sm" className="w-36" />
      </div>
      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_18.75rem]">
        <div className="space-y-4">
          <SkeletonText size="body-sm" className="w-full max-w-xl" />
          <Skeleton className="h-64 rounded-lg" />
          <Skeleton className="h-48 rounded-lg" />
        </div>
        <div className="space-y-4">
          <Skeleton className="h-44 rounded-lg" />
          <Skeleton className="h-60 rounded-lg" />
        </div>
      </div>
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
      <Frame width="max-w-4xl" label="Đang mở biểu mẫu…">
        <SkeletonText size="body-sm" className="w-44" />
        <Heading />
        <div className="grid items-start gap-6 md:grid-cols-[minmax(0,1fr)_15rem]">
          <Skeleton className="h-64 rounded-lg" />
          <Skeleton className="h-40 rounded-lg" />
        </div>
      </Frame>
    );
  }
  return <CourseEditorSkeleton />;
}
