"use client";

import { useQuery } from "@tanstack/react-query";

import { CourseCard } from "@/components/courses/course-card";
import {
  CourseBlock,
  CourseBlockSkeleton,
} from "@/components/recommendations/course-block";
import { getNextCourses } from "@/lib/api/recommendations";

const TITLE = "Học tiếp theo";
const LIMIT = 3;

/**
 * "Học tiếp theo": shown once the whole course is finished.
 *
 * The courses nearest this one that the reader does not have yet -- the
 * leaving-out happens in the backend's query, so a reader who already took
 * the nearest three still gets a full row rather than an empty one.
 *
 * Draws nothing when the course has no vector yet or the request fails: this
 * sits under a finished course, and an error box there would be louder than
 * the thing it is failing to suggest.
 */
export function NextCourses({
  courseId,
  accessToken,
}: {
  courseId: string;
  accessToken: string;
}) {
  const query = useQuery({
    queryKey: ["next-courses", courseId],
    queryFn: () => getNextCourses(accessToken, courseId, LIMIT),
  });

  if (query.isPending) {
    return <CourseBlockSkeleton title={TITLE} count={LIMIT} columns={3} />;
  }
  if (query.isError || query.data.items.length === 0) return null;

  return (
    <CourseBlock
      title={TITLE}
      description="Bạn đã hoàn thành khóa học này. Đây là những khóa gần với nó nhất mà bạn chưa học."
      columns={3}
    >
      {query.data.items.map((item) => (
        <CourseCard key={item.id} course={item} />
      ))}
    </CourseBlock>
  );
}
