import type { Metadata } from "next";

import { BecomeInstructorCard } from "@/components/auth/become-instructor-card";

export const metadata: Metadata = {
  title: "Trở thành giảng viên — DevPath",
  description:
    "Nâng cấp tài khoản DevPath để tạo khóa học, ra bài tập code và theo dõi học viên.",
};

export default function BecomeInstructorPage() {
  return (
    <div className="mx-auto max-w-2xl px-4 py-12">
      <BecomeInstructorCard />
    </div>
  );
}
