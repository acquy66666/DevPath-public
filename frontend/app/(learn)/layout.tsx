import type { ReactNode } from "react";

import { SiteHeader } from "@/components/layout/site-header";

/**
 * No footer here: this is a room to work in, not a page to browse. The header
 * stays so the account menu and the way out are always in the same place.
 */
export default function LearnLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <SiteHeader />
      <main className="flex-1">{children}</main>
    </>
  );
}
