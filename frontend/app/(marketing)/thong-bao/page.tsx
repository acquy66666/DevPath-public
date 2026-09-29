import type { Metadata } from "next";

import { NotificationList } from "@/components/notifications/notification-list";

export const metadata: Metadata = {
  title: "Thông báo — DevPath",
  description: "Thông báo của bạn trên DevPath.",
  robots: { index: false },
};

export default function NotificationsPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-10">
      <h1 className="mb-6 text-3xl font-semibold tracking-tight">Thông báo</h1>
      <NotificationList />
    </div>
  );
}
