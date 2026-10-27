import type { Metadata } from "next";

import { CourseList } from "@/components/instructor/course-list";

export const metadata: Metadata = {
  title: "Giảng dạy — DevPath",
  description: "Quản lý các khóa học bạn đang giảng dạy trên DevPath.",
};

export default function InstructorCoursesPage() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-6 sm:py-8">
      <CourseList />
    </div>
  );
}
