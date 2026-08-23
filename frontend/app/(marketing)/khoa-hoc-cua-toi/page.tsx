import type { Metadata } from "next";

import { MyCourses } from "@/components/enrollments/my-courses";

export const metadata: Metadata = {
  title: "Khóa học của tôi — DevPath",
  description: "Những khóa học bạn đã đăng ký trên DevPath.",
  // Nothing here belongs to anyone but the reader, and a crawler signed in as
  // nobody would only ever see the "đăng nhập" card.
  robots: { index: false },
};

export default function MyCoursesPage() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="mb-6 text-3xl font-semibold tracking-tight">Khóa học của tôi</h1>
      <MyCourses />
    </div>
  );
}
