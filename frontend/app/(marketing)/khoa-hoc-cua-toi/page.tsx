import type { Metadata } from "next";

import { MyCourses } from "@/components/enrollments/my-courses";
import { StudyStats } from "@/components/gamification/study-stats";
import { RecommendedForYou } from "@/components/recommendations/recommended-for-you";

export const metadata: Metadata = {
  title: "Khóa học của tôi — DevPath",
  description: "Những khóa học bạn đã đăng ký trên DevPath.",
  // Nothing here belongs to anyone but the reader, and a crawler signed in as
  // nobody would only ever see the "đăng nhập" card.
  robots: { index: false },
};

/**
 * The learner's own courses, with their achievements beside them.
 *
 * The achievements come first in the page: on a phone they sit above the
 * list, and from `lg` they move to a column on the right while the courses --
 * the page's content -- take the wide one. The column is `auto` wide and the
 * achievements give it its 22rem, so a signed-out visitor, who gets no
 * achievements, gets the whole width for the sign-in card.
 */
export default function MyCoursesPage() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="text-h1 text-balance">Khóa học của tôi</h1>
      <div className="mt-6 grid gap-8 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-start">
        <div className="min-w-0 empty:hidden lg:col-start-2 lg:row-start-1">
          <StudyStats />
        </div>
        <div className="flex min-w-0 flex-col gap-12 lg:col-start-1 lg:row-start-1">
          <MyCourses />
          <RecommendedForYou columns={2} />
        </div>
      </div>
    </div>
  );
}
