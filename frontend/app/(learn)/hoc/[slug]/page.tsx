import type { Metadata } from "next";

import { LearnView } from "@/components/learn/learn-view";
import { getCourseBySlug, type CourseDetail } from "@/lib/api/courses";
import { getCurriculum, type Curriculum } from "@/lib/api/curriculum";

export const metadata: Metadata = {
  title: "Đang học — DevPath",
  // Everything on this page belongs to one enrolled reader, and a crawler is
  // signed in as nobody.
  robots: { index: false },
};

/**
 * `?bai=` picks the lesson, and `?hoi-dap=` opens one of its questions. A query parameter rather than another path segment
 * because the lesson is a position inside this page, not a page of its own --
 * and because it keeps one component in charge of the player, the table of
 * contents and the progress they share.
 */
export default async function LearnPage({
  params,
  searchParams,
}: {
  params: Promise<{ slug: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { slug } = await params;
  const query = await searchParams;
  const lessonId = first(query.bai);
  const threadId = first(query["hoi-dap"]);
  const { course, curriculum } = await loadOutline(slug);

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <LearnView
        slug={slug}
        lessonId={lessonId}
        threadId={threadId}
        initialCourse={course}
        initialCurriculum={curriculum}
      />
    </div>
  );
}

/**
 * The public half of the page, fetched here so it arrives with the HTML: the
 * course and its table of contents are the same for a visitor and an enrolled
 * reader (a token only matters for a course not yet published). With them the
 * lesson title -- the largest thing on screen -- is drawn before the browser
 * has even restored the session, and the reader's progress is asked for
 * straight after it, instead of after a round trip for the course id.
 *
 * Anything that goes wrong here is left to the client, which asks again with
 * the reader's token and shows the error it gets: a draft only its owner may
 * open, a backend that blinked.
 */
async function loadOutline(
  slug: string,
): Promise<{ course: CourseDetail | null; curriculum: Curriculum | null }> {
  try {
    const course = await getCourseBySlug(slug);
    return { course, curriculum: await getCurriculum(course.id) };
  } catch {
    return { course: null, curriculum: null };
  }
}

function first(value: string | string[] | undefined): string | null {
  return Array.isArray(value) ? (value[0] ?? null) : (value ?? null);
}
