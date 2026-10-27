import type { Metadata } from "next";
import Link from "next/link";

import { CourseCreateForm } from "@/components/instructor/course-create-form";

export const metadata: Metadata = {
  title: "Tạo khóa học mới — DevPath",
  description: "Đặt tên và chọn danh mục để bắt đầu một khóa học trên DevPath.",
};

const NEXT_STEPS = [
  "Soạn mục lục: chương, rồi bài học",
  "Viết mô tả, chọn trình độ và giá",
  "Gửi duyệt: quản trị viên xem rồi đưa lên trang công khai",
];

export default function NewCoursePage() {
  return (
    <div className="mx-auto max-w-4xl space-y-5 px-4 py-6 sm:py-8">
      <nav aria-label="Vị trí" className="text-body-sm text-muted-foreground">
        <ol className="flex items-center gap-1.5">
          <li>
            <Link href="/giang-day" className="hover:text-foreground hover:underline">
              Khóa học
            </Link>
          </li>
          <li aria-hidden>/</li>
          <li className="text-foreground" aria-current="page">
            Khóa học mới
          </li>
        </ol>
      </nav>
      <div className="space-y-1.5">
        <h1 className="text-h2 sm:text-h1">Tạo khóa học mới</h1>
        <p className="text-body text-muted-foreground">
          Chỉ cần tên và danh mục. Khóa học ở dạng nháp cho tới khi bạn gửi duyệt.
        </p>
      </div>
      <div className="grid items-start gap-6 md:grid-cols-[minmax(0,1fr)_15rem]">
        <CourseCreateForm />
        <aside aria-labelledby="after-create" className="space-y-3">
          <h2 id="after-create" className="text-body-sm font-semibold">
            Sau bước này
          </h2>
          <ol className="space-y-3">
            {NEXT_STEPS.map((step, index) => (
              <li key={step} className="flex gap-2.5 text-body-sm text-muted-foreground">
                <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-secondary text-xs font-semibold text-secondary-foreground">
                  {index + 1}
                </span>
                {step}
              </li>
            ))}
          </ol>
        </aside>
      </div>
    </div>
  );
}
