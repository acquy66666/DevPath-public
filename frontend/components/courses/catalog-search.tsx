import { Search } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { CatalogQuery } from "@/lib/api/courses";

/** The id the refinement selects point at with `form=`, from elsewhere on the page. */
export const CATALOG_FORM_ID = "catalog-form";

/**
 * The search box at the top of the catalogue, as a plain GET form.
 *
 * No `"use client"` and no router push: submitting navigates to the same page
 * with the fields in the query string, which is what the server reads anyway.
 * Every filtered view stays a URL people can share, and the page works with
 * JavaScript turned off.
 *
 * The topic chosen with the pills rides along as a hidden field, so searching
 * keeps it. The price, rating and sort selects live beside the results
 * (`CatalogRefine`) and join this form through their `form` attribute.
 * `page` is deliberately not a field: a new search starts at page one.
 */
export function CatalogSearch({ query }: { query: CatalogQuery }) {
  return (
    <form
      id={CATALOG_FORM_ID}
      method="get"
      action="/khoa-hoc"
      role="search"
      className="flex max-w-3xl flex-wrap gap-2"
    >
      <label htmlFor="catalog-q" className="sr-only">
        Tìm kiếm
      </label>
      <div className="relative min-w-0 flex-[1_1_16rem]">
        <Search
          className="pointer-events-none absolute top-1/2 left-3.5 size-4.5 -translate-y-1/2 text-muted-foreground"
          aria-hidden
        />
        <Input
          id="catalog-q"
          name="q"
          type="search"
          defaultValue={query.q ?? ""}
          placeholder="python, thuật toán, web…"
          className="h-12 pl-10"
        />
      </div>
      {query.category_id ? <input type="hidden" name="category_id" value={query.category_id} /> : null}
      <Button type="submit" size="lg" className="h-12">
        Tìm
      </Button>
    </form>
  );
}
