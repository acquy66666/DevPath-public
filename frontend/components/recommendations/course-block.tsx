import type { ReactNode } from "react";

/**
 * The frame the three recommender blocks share: a heading, one line saying
 * where the cards came from, and a row of course cards.
 *
 * No empty state on purpose. Each block is a suggestion beside the page's real
 * content, and "we have nothing to suggest" is not worth the space -- the
 * callers draw no block at all instead.
 */
export function CourseBlock({
  title,
  description,
  columns = 4,
  children,
}: {
  title: string;
  description?: ReactNode;
  columns?: 3 | 4;
  children: ReactNode;
}) {
  return (
    <section className="space-y-4" aria-label={title}>
      <header className="space-y-1">
        <h2 className="text-xl font-semibold tracking-tight">{title}</h2>
        {description ? (
          <p className="text-sm text-muted-foreground">{description}</p>
        ) : null}
      </header>
      <div className={gridClass(columns)}>{children}</div>
    </section>
  );
}

/** Card-shaped placeholders, so the page does not jump when the row arrives. */
export function CourseBlockSkeleton({
  title,
  count,
  columns = 4,
}: {
  title: string;
  count: number;
  columns?: 3 | 4;
}) {
  return (
    <section className="space-y-4" aria-label={title} aria-busy>
      <h2 className="text-xl font-semibold tracking-tight">{title}</h2>
      <div className={gridClass(columns)}>
        {Array.from({ length: count }, (_, index) => (
          <div key={index} className="h-72 animate-pulse rounded-xl border bg-muted/40" />
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
