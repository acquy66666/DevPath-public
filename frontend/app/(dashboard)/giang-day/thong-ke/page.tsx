import type { Metadata } from "next";

import { StatsDashboard } from "@/components/instructor/stats/stats-dashboard";

export const metadata: Metadata = {
  title: "Thống kê giảng dạy — DevPath",
  description: "Doanh thu, học viên mới và tỉ lệ hoàn thành của các khóa học bạn dạy.",
};

export default function InstructorStatsPage() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-12">
      <StatsDashboard />
    </div>
  );
}
