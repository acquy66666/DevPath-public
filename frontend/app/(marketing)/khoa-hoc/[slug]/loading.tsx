/**
 * Three server round trips stand between a click and this page: the course,
 * its curriculum and its reviews. The two-column shape is drawn first so the
 * enrol card does not jump in from the side once they answer.
 */
export default function Loading() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-10">
      <div className="mb-6 h-5 w-52 animate-pulse rounded bg-muted/70" />

      <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="space-y-6">
          <div className="h-6 w-28 animate-pulse rounded-full bg-muted" />
          <div className="h-10 w-4/5 animate-pulse rounded-lg bg-muted" />
          <div className="h-5 w-2/3 animate-pulse rounded bg-muted/70" />
          <div className="h-48 animate-pulse rounded-xl border bg-muted/40" />
          {[0, 1, 2].map((row) => (
            <div
              key={row}
              className="h-16 animate-pulse rounded-lg border bg-muted/40"
              aria-hidden
            />
          ))}
        </div>
        <aside className="h-80 animate-pulse rounded-xl border bg-muted/40" aria-hidden />
      </div>
      <span className="sr-only">Đang tải khóa học…</span>
    </div>
  );
}
