import { Badge } from "@/components/ui/badge";
import type { CourseStatus } from "@/lib/api/courses";

/** Vietnamese label and a colour per status, so the list reads at a glance. */
const STATUS: Record<
  CourseStatus,
  { label: string; variant: "default" | "secondary" | "outline" | "destructive" }
> = {
  draft: { label: "Bản nháp", variant: "secondary" },
  pending_review: { label: "Chờ duyệt", variant: "outline" },
  published: { label: "Đã xuất bản", variant: "default" },
  rejected: { label: "Bị từ chối", variant: "destructive" },
};

export function CourseStatusBadge({ status }: { status: CourseStatus }) {
  const { label, variant } = STATUS[status];
  return <Badge variant={variant}>{label}</Badge>;
}
