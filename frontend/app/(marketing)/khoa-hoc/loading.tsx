/**
 * The catalogue fetches courses and categories on the server, so the browser
 * would otherwise sit on the previous page until both answer. Same grid, same
 * gaps, so the real cards land where the grey ones were instead of shoving the
 * page around.
 */
export default function Loading() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <header className="mb-6 space-y-2">
        <div className="h-9 w-44 animate-pulse rounded-lg bg-muted" />
        <div className="h-5 w-64 animate-pulse rounded bg-muted/70" />
      </header>

      <div className="space-y-8">
        <div className="h-11 animate-pulse rounded-xl border bg-muted/40" />
        <ul className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2, 3, 4, 5].map((card) => (
            <li
              key={card}
              className="h-72 animate-pulse rounded-xl border bg-muted/40"
              aria-hidden
            />
          ))}
        </ul>
      </div>
      <span className="sr-only">Đang tải danh sách khóa học…</span>
    </div>
  );
}
