"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/button";

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
      <Button
        type="button"
        variant="ghost"
        size="sm"
        onClick={() => onPage(page - 1)}
        disabled={page <= 1}
      >
        <ChevronLeft data-icon="inline-start" aria-hidden />
        Trang trước
      </Button>
      <span className="text-muted-foreground tabular-nums">
        Trang {page} / {pageCount}
      </span>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        onClick={() => onPage(page + 1)}
        disabled={page >= pageCount}
      >
        Trang sau
        <ChevronRight data-icon="inline-end" aria-hidden />
      </Button>
    </nav>
  );
}
