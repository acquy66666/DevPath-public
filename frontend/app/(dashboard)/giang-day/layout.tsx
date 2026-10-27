import type { ReactNode } from "react";

import { InstructorGate } from "@/components/instructor/instructor-gate";
import { InstructorNav } from "@/components/instructor/instructor-nav";

export default function InstructorLayout({ children }: { children: ReactNode }) {
  return (
    <InstructorGate>
      <InstructorNav />
      {children}
    </InstructorGate>
  );
}
