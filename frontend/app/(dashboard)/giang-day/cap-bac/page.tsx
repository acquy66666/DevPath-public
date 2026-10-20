import type { Metadata } from "next";

import { MyTier } from "@/components/instructor/tier/my-tier";

export const metadata: Metadata = {
  title: "Cấp giảng viên — DevPath",
  description: "Cấp hiện tại, tỉ lệ chia của từng cấp và tiến độ lên cấp kế tiếp.",
};

export default function InstructorTierPage() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-12">
      <MyTier />
    </div>
  );
}
