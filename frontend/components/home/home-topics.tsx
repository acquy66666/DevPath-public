import { connection } from "next/server";

import { TopicLinks } from "@/components/courses/topic-links";
import { Skeleton } from "@/components/ui/skeleton";
import { listCategories, type CategoryTree } from "@/lib/api/categories";

const TITLE = "Duyệt theo chủ đề";

/**
 * "Duyệt theo chủ đề": every category, one click from a filtered catalogue.
 * The welcome page shows the same list under its own title.
 *
 * Streamed at request time like the rows around it: an admin may add a
 * category at any moment, and a build-time list would keep showing the old
 * tree. A failed fetch draws nothing -- the catalogue link in the hero is
 * still there.
 */
export async function HomeTopics({ title = TITLE, id = "home-topics" }: { title?: string; id?: string } = {}) {
  await connection();

  let categories: CategoryTree[] = [];
  try {
    categories = await listCategories();
  } catch {
    return null;
  }
  if (categories.length === 0) return null;

  return (
    <section aria-labelledby={id} className="space-y-4">
      <h2 id={id} className="text-h2">
        {title}
      </h2>
      <TopicLinks
        categories={categories}
        hrefFor={(category) => `/khoa-hoc?category_id=${encodeURIComponent(category)}`}
        label={title}
      />
    </section>
  );
}

/**
 * The heading and a row of pills about as wide as the seed taxonomy's names,
 * so they wrap onto as many lines as the real ones on a phone.
 */
export function HomeTopicsSkeleton({ title = TITLE }: { title?: string } = {}) {
  return (
    <section aria-label={title} aria-busy className="space-y-4">
      <h2 className="text-h2">{title}</h2>
      <div aria-hidden className="flex flex-wrap gap-2">
        {[30, 21, 21, 38, 18, 26, 37, 58].map((width, index) => (
          <Skeleton key={index} className="h-9 rounded-full" style={{ width: `${width * 4}px` }} />
        ))}
      </div>
    </section>
  );
}
