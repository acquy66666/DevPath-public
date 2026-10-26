import { courseSlugFromPath } from "@/lib/account/welcome";
import { getCourseBySlug } from "@/lib/api/courses";

/**
 * The title of the course `next` points at, for "Quay lại …". A nicety only:
 * any failure (not a course path, a course that is gone, the API down) is
 * `null`, and the caller falls back to a sentence without a name.
 */
export async function courseTitleFor(next: string): Promise<string | null> {
  const slug = courseSlugFromPath(next);
  if (!slug) return null;
  try {
    return (await getCourseBySlug(slug)).title;
  } catch {
    return null;
  }
}
