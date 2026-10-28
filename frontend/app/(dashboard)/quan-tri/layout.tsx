import type { Metadata } from "next";
import type { ReactNode } from "react";

import { AdminFrame } from "@/components/admin/admin-frame";
import { AdminGate } from "@/components/admin/admin-gate";
import { AdminNav } from "@/components/admin/admin-nav";

export const metadata: Metadata = {
  title: "Quản trị — DevPath",
  robots: { index: false },
};

export default function AdminLayout({ children }: { children: ReactNode }) {
  return (
    <AdminGate>
      <AdminFrame>
        <AdminNav />
        <div className="min-w-0 flex-1 space-y-6">{children}</div>
      </AdminFrame>
    </AdminGate>
  );
}
