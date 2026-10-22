import Link from "next/link";

import type { CategoryTree } from "@/lib/api/categories";
import { cn } from "@/lib/utils";

/** Every category, a parent followed by its children: the order of the tree. */
export function flattenCategories(categories: CategoryTree[]) {
  return categories.flatMap((parent) => [parent, ...parent.children]);
}

/**
 * The categories as a row of pills, each a link to the catalogue already
 * filtered. Plain links, so the row works without JavaScript and a crawler
 * follows every one.
 *
 * `hrefFor` builds the link (the catalogue keeps the search words when the
 * topic changes); `current` marks the one being shown, `null` for "all".
 * Without `allHref` there is no "Tất cả" pill -- the home page has nothing to
 * reset.
 */
export function TopicLinks({
  categories,
  hrefFor,
  current,
  allHref,
  label = "Chủ đề",
  className,
}: {
  categories: CategoryTree[];
  hrefFor: (categoryId: string) => string;
  current?: string | null;
  allHref?: string;
  label?: string;
  className?: string;
}) {
  const topics = flattenCategories(categories);
  if (topics.length === 0) return null;

  return (
    <nav aria-label={label} className={cn("min-w-0", className)}>
      <ul className="flex flex-wrap gap-2">
        {allHref ? (
          <li>
            <Pill href={allHref} active={!current}>
              Tất cả
            </Pill>
          </li>
        ) : null}
        {topics.map((topic) => (
          <li key={topic.id}>
            <Pill href={hrefFor(topic.id)} active={current === topic.id}>
              {topic.name}
            </Pill>
          </li>
        ))}
      </ul>
    </nav>
  );
}

function Pill({ href, active, children }: { href: string; active: boolean; children: string }) {
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "inline-flex h-9 items-center rounded-full border px-3.5 text-body-sm font-medium whitespace-nowrap transition-colors duration-fast",
        active
          ? "border-primary bg-secondary text-secondary-foreground"
          : "border-border bg-card text-foreground hover:bg-accent",
      )}
    >
      {children}
    </Link>
  );
}
