import type { Metadata } from "next";

import { CourseEditor } from "@/components/instructor/course-editor";

export const metadata: Metadata = {
  title: "Chỉnh sửa khóa học — DevPath",
  // The course itself is private until published, so there is nothing here for
  // a crawler to index -- and nothing that should be indexed either.
  robots: { index: false },
};

export default async function EditCoursePage({
  params,
}: {
  params: Promise<{ courseId: string }>;
}) {
  const { courseId } = await params;
  return (
    <div className="mx-auto max-w-4xl px-4 py-12">
      <CourseEditor courseId={courseId} />
    </div>
  );
}
