/**
 * The catalogue fetches courses and categories on the server, so the browser
 * would otherwise sit on the previous page until both answer. Same grid, same
 * gaps, so the real cards land where the grey ones were instead of shoving the
 * page around.
 *
 * It lives in the `(danh-sach)` group, not in `khoa-hoc/` itself, because a
 * `loading.tsx` wraps every segment below it: one level up it also wrapped
 * `khoa-hoc/[slug]`, whose page then streamed before it knew whether the course
 * exists, so an unpublished or mistyped course answered 200 instead of 404.
 */
export default function Loading() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <header className="mb-6 space-y-2">
        <div className="h-9 w-44 animate-pulse rounded-md bg-muted" />
        <div className="h-5 w-64 animate-pulse rounded bg-muted/70" />
      </header>

      <div className="space-y-8">
        <div className="h-11 animate-pulse rounded-lg border bg-muted/40" />
        <ul className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2, 3, 4, 5].map((card) => (
            <li
              key={card}
              className="h-72 animate-pulse rounded-lg border bg-muted/40"
              aria-hidden
            />
          ))}
        </ul>
      </div>
      <span className="sr-only">Đang tải danh sách khóa học…</span>
    </div>
  );
}
