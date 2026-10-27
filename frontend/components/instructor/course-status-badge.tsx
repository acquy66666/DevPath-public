import { Badge } from "@/components/ui/badge";
import type { CourseStatus } from "@/lib/api/courses";

/**
 * Vietnamese label and a semantic colour per status, so a list reads at a
 * glance: live is green, sent back is red, waiting on the admin is blue, a
 * draft is plain.
 */
const STATUS: Record<
  CourseStatus,
  { label: string; variant: "success" | "muted" | "info" | "destructive" }
> = {
  draft: { label: "Bản nháp", variant: "muted" },
  pending_review: { label: "Chờ duyệt", variant: "info" },
  published: { label: "Đã xuất bản", variant: "success" },
  rejected: { label: "Bị từ chối", variant: "destructive" },
};

export function CourseStatusBadge({ status }: { status: CourseStatus }) {
  const { label, variant } = STATUS[status];
  return <Badge variant={variant}>{label}</Badge>;
}
