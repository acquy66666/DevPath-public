import { Search } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import type { CategoryTree } from "@/lib/api/categories";
import type { CatalogQuery } from "@/lib/api/courses";

/** Ceilings people actually think in, in đồng. `0` is the free-only case. */
const PRICE_CEILINGS = [
  { value: "0", label: "Miễn phí" },
  { value: "200000", label: "Dưới 200.000 ₫" },
  { value: "500000", label: "Dưới 500.000 ₫" },
  { value: "1000000", label: "Dưới 1.000.000 ₫" },
];

const RATING_FLOORS = [
  { value: "4.5", label: "Từ 4,5 sao" },
  { value: "4", label: "Từ 4 sao" },
  { value: "3", label: "Từ 3 sao" },
];

const SORTS = [
  { value: "newest", label: "Mới nhất" },
  { value: "rating", label: "Đánh giá cao" },
  { value: "relevance", label: "Liên quan nhất" },
];

/**
 * The filter bar, as a plain GET form.
 *
 * No `"use client"` and no router push: submitting navigates to the same page
 * with the fields in the query string, which is what the server reads anyway.
 * That keeps the catalogue a Server Component, makes every filtered view a URL
 * people can share, and leaves the page working with JavaScript turned off.
 *
 * `page` is deliberately not a field here — changing a filter should start
 * again at page one, and dropping it from the form is what does that.
 */
export function CatalogFilters({
  categories,
  query,
  filtered,
}: {
  categories: CategoryTree[];
  query: CatalogQuery;
  filtered: boolean;
}) {
  return (
    <form
      method="get"
      action="/khoa-hoc"
      // Two across from the smallest screen up, with the search box and the
      // buttons spanning both: one field per row made a phone scroll a full
      // screen of filters before the first course.
      className="grid grid-cols-2 gap-3 rounded-lg border p-4 lg:grid-cols-[minmax(0,2fr)_repeat(4,minmax(0,1fr))_auto] lg:items-end"
    >
      <div className="col-span-2 space-y-1.5 lg:col-span-1">
        <Label htmlFor="catalog-q">Tìm kiếm</Label>
        <div className="relative">
          <Search
            className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden
          />
          <Input
            id="catalog-q"
            name="q"
            type="search"
            defaultValue={query.q ?? ""}
            placeholder="python, thuật toán, web…"
            className="pl-8"
          />
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="catalog-category">Danh mục</Label>
        <NativeSelect
          id="catalog-category"
          name="category_id"
          defaultValue={query.category_id ?? ""}
        >
          <option value="">Tất cả</option>
          {categories.map((parent) => (
            <optgroup key={parent.id} label={parent.name}>
              <option value={parent.id}>Toàn bộ {parent.name}</option>
              {parent.children.map((child) => (
                <option key={child.id} value={child.id}>
                  {child.name}
                </option>
              ))}
            </optgroup>
          ))}
        </NativeSelect>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="catalog-price">Giá</Label>
        <NativeSelect
          id="catalog-price"
          name="price_max"
          defaultValue={query.price_max ?? ""}
        >
          <option value="">Mọi mức giá</option>
          {PRICE_CEILINGS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </NativeSelect>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="catalog-rating">Đánh giá</Label>
        <NativeSelect
          id="catalog-rating"
          name="rating_min"
          defaultValue={query.rating_min ?? ""}
        >
          <option value="">Mọi đánh giá</option>
          {RATING_FLOORS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </NativeSelect>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="catalog-sort">Sắp xếp</Label>
        <NativeSelect id="catalog-sort" name="sort" defaultValue={query.sort ?? ""}>
          <option value="">Mặc định</option>
          {SORTS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </NativeSelect>
      </div>

      <div className="col-span-2 flex items-center gap-3 lg:col-span-1">
        <Button type="submit">Lọc</Button>
        {filtered ? (
          <Link
            href="/khoa-hoc"
            className="text-sm text-muted-foreground underline-offset-4 hover:underline"
          >
            Xóa lọc
          </Link>
        ) : null}
      </div>
    </form>
  );
}
