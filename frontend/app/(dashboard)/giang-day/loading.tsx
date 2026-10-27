"use client";

import { usePathname } from "next/navigation";

import { instructorSkeletonFor } from "@/components/instructor/instructor-skeletons";

/**
 * The skeleton of whichever instructor screen is opening. This file wraps
 * every route under /giang-day that has no loading.tsx of its own (the editor,
 * the new-course form, the tier page), so it asks the path instead of always
 * drawing the overview -- the same choice the gate makes.
 */
export default function Loading() {
  return instructorSkeletonFor(usePathname());
}
