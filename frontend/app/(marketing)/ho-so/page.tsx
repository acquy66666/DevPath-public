import type { Metadata } from "next";

import { ProfileView } from "@/components/profile/profile-view";

export const metadata: Metadata = {
  title: "Hồ sơ của tôi — DevPath",
  description: "Xem và cập nhật thông tin tài khoản DevPath của bạn.",
};

export default function ProfilePage() {
  return (
    <div className="mx-auto max-w-2xl px-4 py-10">
      <h1 className="mb-6 text-3xl font-semibold tracking-tight">Hồ sơ của tôi</h1>
      <ProfileView />
    </div>
  );
}
