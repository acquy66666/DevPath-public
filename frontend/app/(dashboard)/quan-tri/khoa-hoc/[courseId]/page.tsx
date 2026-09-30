import { AdminCourseReview } from "@/components/admin/admin-course-review";

export default async function AdminCourseReviewPage({
  params,
}: {
  params: Promise<{ courseId: string }>;
}) {
  const { courseId } = await params;
  return <AdminCourseReview courseId={courseId} />;
}
