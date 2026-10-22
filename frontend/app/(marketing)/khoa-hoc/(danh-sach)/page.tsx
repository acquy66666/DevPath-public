import type { Metadata } from "next";
import Link from "next/link";
import { cache } from "react";

import { CatalogFilters } from "@/components/courses/catalog-filters";
import { CatalogPagination } from "@/components/courses/catalog-pagination";
import { CourseCard } from "@/components/courses/course-card";
import { listCategories } from "@/lib/api/categories";
import {
  catalogSearchParams,
  listCourses,
  type CatalogQuery,
  type CatalogSort,
} from "@/lib/api/courses";

/**
 * The catalogue. Server-rendered, and every filtered view is a real URL.
 *
 * There is no `loading.tsx` in this folder on purpose: a skeleton here would
 * become a Suspense boundary for `khoa-hoc/[slug]` as well, and that page
 * depends on nothing streaming before it can answer a real 404. The reason is
 * written out in full at the top of `[slug]/page.tsx`.
 */

/** A grid of three or four columns divides neatly either way. */
const PAGE_SIZE = 12;

const SORTS: CatalogSort[] = ["relevance", "newest", "rating"];

type RawSearchParams = Record<string, string | string[] | undefined>;

function first(value: string | string[] | undefined): string | undefined {
  const text = Array.isArray(value) ? value[0] : value;
  const trimmed = text?.trim();
  return trimmed ? trimmed : undefined;
}

/**
 * Keep only what looks like a number.
 *
 * These land in the URL, where anyone may edit them. The backend would answer
 * 422 to `price_max=cheap`, which is correct for an API and wrong for a page
 * someone is browsing -- dropping the nonsense shows the catalogue instead of
 * an error.
 */
function numeric(value: string | undefined): string | undefined {
  return value !== undefined && /^\d+(\.\d+)?$/.test(value) ? value : undefined;
}

function parseQuery(raw: RawSearchParams): { query: CatalogQuery; page: number } {
  const sort = first(raw.sort);
  const page = Number.parseInt(first(raw.page) ?? "1", 10);

  return {
    query: {
      q: first(raw.q),
      category_id: first(raw.category_id),
      price_min: numeric(first(raw.price_min)),
      price_max: numeric(first(raw.price_max)),
      rating_min: numeric(first(raw.rating_min)),
      sort: SORTS.includes(sort as CatalogSort) ? (sort as CatalogSort) : undefined,
    },
    page: Number.isNaN(page) || page < 1 ? 1 : page,
  };
}

/** Anything narrowing the catalogue, sorting aside. */
function isFiltered(query: CatalogQuery): boolean {
  return Boolean(
    query.q || query.category_id || query.price_min || query.price_max || query.rating_min,
  );
}

const loadCategories = cache(listCategories);

export async function generateMetadata({
  searchParams,
}: {
  searchParams: Promise<RawSearchParams>;
}): Promise<Metadata> {
  const { query, page } = parseQuery(await searchParams);
  const params = catalogSearchParams({ ...query, page: page > 1 ? page : undefined });
  const canonical = params.size > 0 ? `/khoa-hoc?${params}` : "/khoa-hoc";

  const title = query.q
    ? `Tìm kiếm "${query.q}" — DevPath`
    : "Khóa học lập trình — DevPath";

  return {
    title,
    description:
      "Duyệt toàn bộ khóa học trên DevPath: tìm theo từ khóa, lọc theo danh mục, mức giá và đánh giá.",
    alternates: { canonical },
    // A filtered view is one of thousands of combinations of the same courses.
    // Let a crawler follow the links, but keep the permutations out of the
    // index; the unfiltered listing and each course page are the pages worth
    // ranking.
    robots: isFiltered(query) ? { index: false, follow: true } : undefined,
  };
}

export default async function CatalogPage({
  searchParams,
}: {
  searchParams: Promise<RawSearchParams>;
}) {
  const { query, page } = parseQuery(await searchParams);

  const [categories, firstTry] = await Promise.all([
    loadCategories(),
    listCourses({ ...query, page, page_size: PAGE_SIZE }),
  ]);

  const pageCount = Math.max(1, Math.ceil(firstTry.total / firstTry.page_size));

  // A page number past the end is a stale link or a hand-edited URL, and the
  // backend answers it honestly with an empty list. Showing "không tìm thấy
  // khóa học nào" over a catalogue that has plenty would be a lie, so ask
  // again for the last real page. Only ever one extra request, and only for a
  // URL that was already wrong.
  const current = Math.min(page, pageCount);
  const results =
    current === page
      ? firstTry
      : await listCourses({ ...query, page: current, page_size: PAGE_SIZE });

  const filtered = isFiltered(query);

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <header className="mb-6 space-y-2">
        <h1 className="text-3xl font-semibold tracking-tight">Khóa học</h1>
        <p className="text-muted-foreground">
          {results.total > 0
            ? `${results.total} khóa học${query.q ? ` cho “${query.q}”` : ""}`
            : "Chưa có khóa học nào khớp với lựa chọn của bạn."}
        </p>
      </header>

      <div className="space-y-8">
        <CatalogFilters categories={categories} query={query} filtered={filtered} />

        {results.items.length > 0 ? (
          <>
            <ul className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {results.items.map((course) => (
                <li key={course.id} className="h-full">
                  <CourseCard course={course} />
                </li>
              ))}
            </ul>

            <CatalogPagination query={query} page={current} pageCount={pageCount} />
          </>
        ) : (
          <div className="rounded-lg border border-dashed p-12 text-center">
            <p className="font-medium">Không tìm thấy khóa học nào</p>
            <p className="mt-1 text-sm text-muted-foreground">
              {filtered
                ? "Thử bớt một bộ lọc, hoặc tìm bằng từ khóa khác."
                : "Các khóa học đầu tiên đang được giảng viên hoàn thiện."}
            </p>
            {filtered ? (
              <Link
                href="/khoa-hoc"
                className="mt-4 inline-block text-sm underline underline-offset-4"
              >
                Xóa toàn bộ bộ lọc
              </Link>
            ) : null}
          </div>
        )}
      </div>
    </div>
  );
}
