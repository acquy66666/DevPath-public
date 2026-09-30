import type { ReactNode } from "react";

import { InstructorGate } from "@/components/instructor/instructor-gate";

export default function InstructorLayout({ children }: { children: ReactNode }) {
  return <InstructorGate>{children}</InstructorGate>;
}
