import type { ReactNode } from "react";

import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";

/**
 * The frame of both back-office areas. Who may be inside is decided one level
 * down -- `giang-day` lets instructors in, `quan-tri` lets admins in -- because
 * the two roles are exact matches on the backend and neither area is a
 * superset of the other.
 */
export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <SiteHeader />
      <main className="flex-1">{children}</main>
      <SiteFooter />
    </>
  );
}
