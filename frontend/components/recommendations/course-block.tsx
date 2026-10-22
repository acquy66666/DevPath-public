import type { ReactNode } from "react";

import { CourseCardSkeleton } from "@/components/courses/course-card";
import { SkeletonText } from "@/components/ui/skeleton";

/**
 * The frame the course rows share (the three recommender blocks and "Khóa
 * học mới"): a heading, one line saying where the cards came from, an
 * optional link on the right, and the cards.
 *
 * `layout="rows"` is for a row that came back with one or two courses: they
 * are drawn on their side (`CourseRowCard`), two across, instead of leaving
 * most of a four-column grid empty.
 *
 * No empty state on purpose. Each block is a suggestion beside the page's real
 * content, and "we have nothing to suggest" is not worth the space -- the
 * callers draw no block at all instead.
 */
export function CourseBlock({
  title,
  description,
  action,
  columns = 4,
  layout = "grid",
  children,
}: {
  title: string;
  description?: ReactNode;
  /** A link beside the heading, e.g. "Xem tất cả khóa học". */
  action?: ReactNode;
  columns?: 3 | 4;
  layout?: "grid" | "rows";
  children: ReactNode;
}) {
  return (
    <section className="space-y-4" aria-label={title}>
      <BlockHeader title={title} description={description} action={action} />
      <div className={layout === "rows" ? "grid gap-5 md:grid-cols-2" : gridClass(columns)}>
        {children}
      </div>
    </section>
  );
}

function BlockHeader({
  title,
  description,
  action,
  describedSkeleton = false,
}: {
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  describedSkeleton?: boolean;
}) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-x-6 gap-y-1">
      <div className="min-w-0 space-y-1">
        <h2 className="text-h2 text-balance">{title}</h2>
        {description ? (
          <p className="text-body-sm text-muted-foreground">{description}</p>
        ) : describedSkeleton ? (
          <SkeletonText size="body-sm" className="w-[min(32rem,80vw)]" />
        ) : null}
      </div>
      {action ? <div className="shrink-0 text-body-sm font-semibold">{action}</div> : null}
    </header>
  );
}

/** Card-shaped placeholders, so the page does not jump when the row arrives. */
export function CourseBlockSkeleton({
  title,
  count,
  columns = 4,
  described = false,
  notes = false,
  action,
}: {
  title: string;
  count: number;
  columns?: 3 | 4;
  /** The block will have a line under its title. */
  described?: boolean;
  /** Each card will say why it is there (the recommender rows). */
  notes?: boolean;
  action?: ReactNode;
}) {
  return (
    <section className="space-y-4" aria-label={title} aria-busy>
      <BlockHeader title={title} action={action} describedSkeleton={described} />
      <div className={gridClass(columns)}>
        {Array.from({ length: count }, (_, index) => (
          <CourseCardSkeleton key={index} note={notes} />
        ))}
      </div>
    </section>
  );
}

function gridClass(columns: 3 | 4): string {
  // Spelled out rather than interpolated: Tailwind only ships the classes it
  // can find written down in the source.
  return columns === 3
    ? "grid gap-5 sm:grid-cols-2 lg:grid-cols-3"
    : "grid gap-5 sm:grid-cols-2 lg:grid-cols-4";
}
