import Link from "next/link";

import { Button } from "@/components/ui/button";
import { catalogSearchParams, type CatalogQuery } from "@/lib/api/courses";

function pageHref(query: CatalogQuery, page: number): string {
  const params = catalogSearchParams({ ...query, page });
  return `/khoa-hoc?${params}`;
}

/**
 * Previous / next as real links, not buttons.
 *
 * Every page of the catalogue is its own URL, so a crawler can walk the whole
 * listing and a reader can bookmark page three. Buttons with an onClick would
 * need `"use client"` and would leave both of them with nothing to follow.
 */
export function CatalogPagination({
  query,
  page,
  pageCount,
}: {
  query: CatalogQuery;
  page: number;
  pageCount: number;
}) {
  if (pageCount <= 1) return null;

  return (
    <nav
      aria-label="Phân trang"
      className="flex items-center justify-center gap-3 pt-4"
    >
      {page > 1 ? (
        <Button variant="outline" size="sm" asChild>
          <Link href={pageHref(query, page - 1)} rel="prev">
            Trang trước
          </Link>
        </Button>
      ) : (
        <Button variant="outline" size="sm" disabled>
          Trang trước
        </Button>
      )}

      <span className="text-sm text-muted-foreground">
        Trang {page} / {pageCount}
      </span>

      {page < pageCount ? (
        <Button variant="outline" size="sm" asChild>
          <Link href={pageHref(query, page + 1)} rel="next">
            Trang sau
          </Link>
        </Button>
      ) : (
        <Button variant="outline" size="sm" disabled>
          Trang sau
        </Button>
      )}
    </nav>
  );
}
