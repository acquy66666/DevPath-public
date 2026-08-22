import type { Metadata } from "next";

import { CourseList } from "@/components/instructor/course-list";

export const metadata: Metadata = {
  title: "Khóa học của tôi — DevPath",
  description: "Quản lý các khóa học bạn đang giảng dạy trên DevPath.",
};

export default function InstructorCoursesPage() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-12">
      <CourseList />
    </div>
  );
}
