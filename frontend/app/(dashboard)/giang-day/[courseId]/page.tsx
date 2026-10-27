import type { Metadata } from "next";

import { CourseEditor, type EditorTab } from "@/components/instructor/course-editor";

export const metadata: Metadata = {
  title: "Chỉnh sửa khóa học — DevPath",
  // The course itself is private until published, so there is nothing here for
  // a crawler to index -- and nothing that should be indexed either.
  robots: { index: false },
};

export default async function EditCoursePage({
  params,
  searchParams,
}: {
  params: Promise<{ courseId: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const [{ courseId }, { tab }] = await Promise.all([params, searchParams]);
  const initialTab: EditorTab = tab === "thong-tin" ? "thong-tin" : "noi-dung";
  return (
    <div className="mx-auto max-w-6xl px-4 py-6 sm:py-8">
      <CourseEditor courseId={courseId} initialTab={initialTab} />
    </div>
  );
}
