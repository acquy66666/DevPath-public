import type { Metadata } from "next";
import Link from "next/link";

import { CourseCreateForm } from "@/components/instructor/course-create-form";

export const metadata: Metadata = {
  title: "Tạo khóa học mới — DevPath",
  description: "Đặt tên và chọn danh mục để bắt đầu một khóa học trên DevPath.",
};

export default function NewCoursePage() {
  return (
    <div className="mx-auto max-w-2xl px-4 py-12">
      <Link
        href="/giang-day"
        className="text-sm text-muted-foreground underline-offset-4 hover:underline"
      >
        ← Khóa học của tôi
      </Link>
      <h1 className="mt-4 mb-2 text-2xl font-semibold tracking-tight">
        Tạo khóa học mới
      </h1>
      <p className="mb-6 text-sm text-muted-foreground">
        Chỉ cần tên và danh mục. Mọi thứ còn lại — mô tả, giá, mục lục — sửa được ở
        bước sau, và khóa học ở dạng nháp cho tới khi bạn gửi duyệt.
      </p>
      <CourseCreateForm />
    </div>
  );
}
