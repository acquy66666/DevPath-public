import type { Metadata } from "next";

import { ProfileView } from "@/components/profile/profile-view";

export const metadata: Metadata = {
  title: "Hồ sơ của tôi — DevPath",
  description: "Xem và cập nhật thông tin tài khoản DevPath của bạn.",
};

export default function ProfilePage() {
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 px-4 pt-8 pb-16 md:gap-8 md:pt-10 md:pb-20">
      <h1 className="text-h1">Hồ sơ của tôi</h1>
      <ProfileView />
    </div>
  );
}
