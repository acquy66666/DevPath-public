import { QaInboxSkeleton } from "@/components/instructor/instructor-skeletons";

/** Same frame as the inbox, so nothing jumps when the questions arrive. */
export default function Loading() {
  return <QaInboxSkeleton />;
}
