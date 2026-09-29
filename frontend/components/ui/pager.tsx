"use client";

/**
 * "Trang 2 / 5" between two buttons, under a paged `{items, total, page,
 * page_size}` list. Draws nothing when everything fits on one page.
 */
export function Pager({
  page,
  pageSize,
  total,
  onPage,
}: {
  page: number;
  pageSize: number;
  total: number;
  onPage: (page: number) => void;
}) {
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  if (pageCount === 1) return null;
  return (
    <nav className="flex items-center justify-between gap-3 text-sm" aria-label="Phân trang">
      <button
        type="button"
        className="rounded-md px-2 py-1 hover:bg-muted disabled:pointer-events-none disabled:opacity-40"
        onClick={() => onPage(page - 1)}
        disabled={page <= 1}
      >
        ← Trang trước
      </button>
      <span className="text-muted-foreground">
        Trang {page} / {pageCount}
      </span>
      <button
        type="button"
        className="rounded-md px-2 py-1 hover:bg-muted disabled:pointer-events-none disabled:opacity-40"
        onClick={() => onPage(page + 1)}
        disabled={page >= pageCount}
      >
        Trang sau →
      </button>
    </nav>
  );
}
