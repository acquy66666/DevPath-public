import Link from "next/link";
import { connection } from "next/server";

import { CourseCard } from "@/components/courses/course-card";
import { CourseBlock, CourseBlockSkeleton } from "@/components/recommendations/course-block";
import { listCourses, type CourseCard as Course } from "@/lib/api/courses";

const TITLE = "Khóa học mới";
/** One row on a wide screen. */
const LIMIT = 4;

/**
 * The newest courses on sale, for everyone who opens the home page -- the one
 * row a signed-out visitor sees before deciding whether to look further.
 *
 * Server Component, streamed behind Suspense: the list is the same for every
 * reader and worth crawling. `connection()` keeps it out of the build-time
 * prerender, which would otherwise freeze the catalogue as it was then.
 *
 * Draws nothing when the catalogue is empty or cannot be read: the hero above
 * already links to `/khoa-hoc`, which has its own empty and error states.
 */
export async function NewestCourses() {
  await connection();

  let items: Course[] = [];
  try {
    items = (await listCourses({ sort: "newest", page_size: LIMIT })).items;
  } catch {
    return null;
  }
  if (items.length === 0) return null;

  return (
    <CourseBlock title={TITLE} description="Vừa lên sàn." action={<AllCoursesLink />}>
      {items.map((course) => (
        <CourseCard key={course.id} course={course} />
      ))}
    </CourseBlock>
  );
}

export function NewestCoursesSkeleton() {
  return <CourseBlockSkeleton title={TITLE} count={LIMIT} described action={<AllCoursesLink />} />;
}

function AllCoursesLink() {
  return (
    <Link href="/khoa-hoc" className="text-link underline-offset-4 hover:underline">
      Xem tất cả khóa học
    </Link>
  );
}
