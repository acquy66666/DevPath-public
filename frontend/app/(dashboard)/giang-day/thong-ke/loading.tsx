import { StatsSkeleton } from "@/components/instructor/instructor-skeletons";

/** Same frame as the dashboard, so nothing jumps when the numbers arrive. */
export default function Loading() {
  return <StatsSkeleton />;
}
