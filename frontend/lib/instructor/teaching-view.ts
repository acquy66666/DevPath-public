// What the instructor area shows about a set of courses, worked out without
// React: counts per status, the things waiting for the instructor, the
// pre-review hints of a course and the summary of its curriculum.
//
// Type imports only: `npm test` runs this file under bare Node, which does not
// resolve extensionless imports at run time (the same rule as
// lib/commerce/cart-view.ts).
import type { Course, CourseStatus } from "@/lib/api/courses";
import type { LessonType, SectionWithLessons } from "@/lib/api/curriculum";

type Teaching = Pick<Course, "id" | "title" | "status">;

/** The filter chips over the course list, in the order they show. */
export const STATUS_FILTERS: Array<{ value: CourseStatus | "all"; label: string }> = [
  { value: "all", label: "Tất cả" },
  { value: "published", label: "Đã xuất bản" },
  { value: "pending_review", label: "Chờ duyệt" },
  { value: "draft", label: "Bản nháp" },
  { value: "rejected", label: "Bị từ chối" },
];

export function statusCounts(courses: Teaching[]): Record<CourseStatus | "all", number> {
  const counts = { all: courses.length, published: 0, pending_review: 0, draft: 0, rejected: 0 };
  for (const course of courses) counts[course.status] += 1;
  return counts;
}

/** The chips worth showing: "all", plus every status that has at least one course. */
export function visibleFilters(courses: Teaching[]) {
  const counts = statusCounts(courses);
  return STATUS_FILTERS.filter((f) => f.value === "all" || counts[f.value] > 0).map((f) => ({
    ...f,
    count: counts[f.value],
  }));
}

export function filterCourses<T extends Teaching>(courses: T[], status: CourseStatus | "all"): T[] {
  return status === "all" ? courses : courses.filter((course) => course.status === status);
}

export type Task =
  | { kind: "questions"; count: number; href: string }
  | { kind: "rejected"; courseId: string; title: string; href: string }
  | { kind: "draft"; courseId: string; title: string; href: string };

/**
 * What is waiting for the instructor, most urgent first: learners who asked
 * and got no answer, then courses an admin sent back, then drafts never sent.
 * Courses waiting for review are the admin's move, so they are not listed.
 */
export function pendingTasks(courses: Teaching[], unanswered: number): Task[] {
  const tasks: Task[] = [];
  if (unanswered > 0) tasks.push({ kind: "questions", count: unanswered, href: "/giang-day/hoi-dap" });
  for (const course of courses) {
    if (course.status === "rejected") {
      tasks.push({ kind: "rejected", courseId: course.id, title: course.title, href: `/giang-day/${course.id}?tab=thong-tin` });
    }
  }
  for (const course of courses) {
    if (course.status === "draft") {
      tasks.push({ kind: "draft", courseId: course.id, title: course.title, href: `/giang-day/${course.id}` });
    }
  }
  return tasks;
}

/** The line under "Chào …". */
export function greetingLine(courses: number, students: number, tasks: number): string {
  if (courses === 0) return "Bắt đầu bằng khóa học đầu tiên: chỉ cần một cái tên và một danh mục.";
  const head = `${courses} khóa học, ${students} học viên.`;
  if (tasks === 0) return `${head} Không có việc nào đang chờ bạn.`;
  return `${head} Có ${tasks} việc đang chờ bạn.`;
}

const TYPE_NAMES: Record<LessonType, string> = {
  video: "video",
  article: "bài đọc",
  code_exercise: "bài tập code",
  quiz: "trắc nghiệm",
};
const TYPE_ORDER: LessonType[] = ["video", "article", "code_exercise", "quiz"];

type Lessons = Pick<SectionWithLessons, "lessons">;

/** "6 bài · 4 video · 1 bài tập code · 1 trắc nghiệm" under a chapter title. */
export function sectionSummary(section: Lessons): string {
  const total = section.lessons.length;
  if (total === 0) return "Chưa có bài nào";
  const parts = [`${total} bài`];
  for (const type of TYPE_ORDER) {
    const n = section.lessons.filter((lesson) => lesson.type === type).length;
    if (n > 0) parts.push(`${n} ${TYPE_NAMES[type]}`);
  }
  return parts.join(" · ");
}

/** The counts in the editor's side card. */
export function curriculumCounts(sections: Lessons[]) {
  const lessons = sections.flatMap((section) => section.lessons);
  return {
    sections: sections.length,
    video: lessons.filter((l) => l.type === "video").length,
    article: lessons.filter((l) => l.type === "article").length,
    code_exercise: lessons.filter((l) => l.type === "code_exercise").length,
    quiz: lessons.filter((l) => l.type === "quiz").length,
    preview: lessons.filter((l) => l.is_preview).length,
  };
}

export interface Check {
  label: string;
  done: boolean;
}

/**
 * Hints before sending a course for review. The backend requires none of
 * these -- an admin decides -- so they are suggestions, never a lock on the
 * button; they are what admins have sent courses back for.
 */
export function reviewChecklist(
  course: Pick<Course, "subtitle" | "description">,
  sections: Lessons[] | undefined,
): Check[] {
  const filled = (text: string | null) => text !== null && text.trim() !== "";
  const list = sections ?? [];
  return [
    { label: "Có mô tả ngắn", done: filled(course.subtitle) },
    { label: "Có mô tả chi tiết", done: filled(course.description) },
    {
      label: "Mỗi chương có ít nhất một bài",
      done: list.length > 0 && list.every((section) => section.lessons.length > 0),
    },
    {
      label: "Có ít nhất một bài cho học thử",
      done: list.some((section) => section.lessons.some((lesson) => lesson.is_preview)),
    },
  ];
}
