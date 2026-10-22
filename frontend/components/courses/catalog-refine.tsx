"use client";

import { SlidersHorizontal } from "lucide-react";
import { useState, type ChangeEvent, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { NativeSelect } from "@/components/ui/native-select";
import type { CatalogQuery } from "@/lib/api/courses";
import { cn } from "@/lib/utils";

import { CATALOG_FORM_ID } from "./catalog-search";

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
 * Price, rating and sort, beside the result count.
 *
 * The selects belong to the search form at the top of the page through their
 * `form` attribute, so one GET carries every field. Changing one submits the
 * form at once; without JavaScript the "Tìm" button above still sends them.
 * On a phone they fold behind a "Bộ lọc" button, so the first course is not a
 * screen of controls away.
 */
export function CatalogRefine({ query }: { query: CatalogQuery }) {
  const [open, setOpen] = useState(false);
  const active = [query.price_max, query.rating_min, query.sort].filter(Boolean).length;

  const submit = (event: ChangeEvent<HTMLSelectElement>) => event.currentTarget.form?.requestSubmit();

  return (
    <div className="flex flex-col items-start gap-3 md:items-end">
      <Button
        type="button"
        variant="outline"
        className="md:hidden"
        aria-expanded={open}
        aria-controls="catalog-refine"
        onClick={() => setOpen((value) => !value)}
      >
        <SlidersHorizontal aria-hidden />
        Bộ lọc{active > 0 ? ` · ${active}` : ""}
      </Button>

      <div
        id="catalog-refine"
        className={cn("w-full flex-wrap items-end gap-3 md:flex md:w-auto", open ? "grid grid-cols-2" : "hidden")}
      >
        <Field id="catalog-price" label="Giá">
          <NativeSelect
            id="catalog-price"
            name="price_max"
            form={CATALOG_FORM_ID}
            defaultValue={query.price_max ?? ""}
            onChange={submit}
          >
            <option value="">Mọi mức giá</option>
            {PRICE_CEILINGS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </NativeSelect>
        </Field>

        <Field id="catalog-rating" label="Đánh giá">
          <NativeSelect
            id="catalog-rating"
            name="rating_min"
            form={CATALOG_FORM_ID}
            defaultValue={query.rating_min ?? ""}
            onChange={submit}
          >
            <option value="">Mọi đánh giá</option>
            {RATING_FLOORS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </NativeSelect>
        </Field>

        <Field id="catalog-sort" label="Sắp xếp" className="col-span-2 md:col-span-1">
          <NativeSelect
            id="catalog-sort"
            name="sort"
            form={CATALOG_FORM_ID}
            defaultValue={query.sort ?? ""}
            onChange={submit}
          >
            <option value="">Mặc định</option>
            {SORTS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </NativeSelect>
        </Field>
      </div>
    </div>
  );
}

/** A label over a control, 6px apart, like FormField. */
function Field({
  id,
  label,
  className,
  children,
}: {
  id: string;
  label: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div className={cn("min-w-0 space-y-1.5 md:w-44", className)}>
      <label htmlFor={id} className="block text-body-sm font-medium text-muted-foreground">
        {label}
      </label>
      {children}
    </div>
  );
}
