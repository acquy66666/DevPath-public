import type { ReactNode } from "react";

import { InstructorGate } from "@/components/instructor/instructor-gate";
import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <SiteHeader />
      <main className="flex-1">
        <InstructorGate>{children}</InstructorGate>
      </main>
      <SiteFooter />
    </>
  );
}
