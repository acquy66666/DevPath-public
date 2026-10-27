import type { Metadata } from "next";

import { StatsDashboard } from "@/components/instructor/stats/stats-dashboard";

export const metadata: Metadata = {
  title: "Thống kê giảng dạy — DevPath",
  description: "Học viên, mức độ học, kết quả và phản hồi của các khóa học bạn dạy.",
};

export default function InstructorStatsPage() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-6 sm:py-8">
      <StatsDashboard />
    </div>
  );
}
