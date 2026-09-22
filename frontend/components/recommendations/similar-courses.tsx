import { CourseCard } from "@/components/courses/course-card";
import { CourseBlock } from "@/components/recommendations/course-block";
import type { SimilarCourse } from "@/lib/api/recommendations";

/**
 * "Khóa học tương tự" on the public course page. A Server Component: the
 * neighbours are public, so they are rendered into the first response along
 * with the rest of the page, and a crawler follows them like any other link.
 *
 * An empty list draws nothing -- it means the course has no vector yet, not
 * that nothing resembles it.
 */
export function SimilarCourses({ items }: { items: SimilarCourse[] }) {
  if (items.length === 0) return null;

  return (
    <CourseBlock
      title="Khóa học tương tự"
      description="Gần nhất với khóa này về nội dung."
      columns={3}
    >
      {items.map((item) => (
        <CourseCard key={item.id} course={item} />
      ))}
    </CourseBlock>
  );
}
