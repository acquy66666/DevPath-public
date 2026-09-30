import type { Metadata } from "next";
import type { ReactNode } from "react";

import { AdminGate } from "@/components/admin/admin-gate";
import { AdminNav } from "@/components/admin/admin-nav";

export const metadata: Metadata = {
  title: "Quản trị — DevPath",
  robots: { index: false },
};

export default function AdminLayout({ children }: { children: ReactNode }) {
  return (
    <AdminGate>
      <div className="mx-auto max-w-5xl space-y-6 px-4 py-10">
        <AdminNav />
        {children}
      </div>
    </AdminGate>
  );
}
