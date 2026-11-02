// What the admin area shows around its screens, worked out without React:
// the grouped places of the side menu, which one a path belongs to, how long a
// course has waited and what the overview lists as waiting.
//
// Type imports only: `npm test` runs this file under bare Node, which does not
// resolve extensionless imports at run time (the same rule as
// lib/instructor/teaching-view.ts).
import type { AdminSummary } from "@/lib/api/admin";

/** Which count of `AdminSummary` a place carries as its badge. */
export type PlaceBadge = "pending_courses" | "pending_reports" | "pending_instructor_applications";

export interface Place {
  href: string;
  label: string;
  badge?: PlaceBadge;
}

export interface PlaceGroup {
  /** Null for the first group, which is the overview alone and has no heading. */
  label: string | null;
  places: Place[];
}

/**
 * Thirteen places in four groups. A row of twelve tabs ran off the side at
 * 1440 px (docs/report/assets/phase-7/before.md); grouped in a side menu they
 * all show, and the work an admin decides on comes first.
 */
export const PLACE_GROUPS: PlaceGroup[] = [
  { label: null, places: [{ href: "/quan-tri", label: "Tổng quan" }] },
  {
    label: "Kiểm duyệt",
    places: [
      { href: "/quan-tri/khoa-hoc", label: "Duyệt khóa học", badge: "pending_courses" },
      {
        href: "/quan-tri/duyet-giang-vien",
        label: "Duyệt giảng viên",
        badge: "pending_instructor_applications",
      },
      { href: "/quan-tri/bao-cao", label: "Báo cáo vi phạm", badge: "pending_reports" },
      { href: "/quan-tri/nguoi-dung", label: "Người dùng" },
    ],
  },
  {
    // Money lives here and nowhere an instructor can reach (20/10/2026).
    label: "Tài chính",
    places: [
      { href: "/quan-tri/doanh-thu", label: "Doanh thu" },
      { href: "/quan-tri/xep-hang", label: "Xếp hạng" },
      { href: "/quan-tri/cap-giang-vien", label: "Cấp giảng viên" },
      { href: "/quan-tri/thanh-toan", label: "Thanh toán giảng viên" },
      { href: "/quan-tri/loi-nhuan", label: "Lợi nhuận" },
    ],
  },
  {
    label: "Nội dung sàn",
    places: [
      { href: "/quan-tri/danh-muc", label: "Danh mục" },
      { href: "/quan-tri/ma-giam-gia", label: "Mã giảm giá" },
      { href: "/quan-tri/banner", label: "Banner" },
    ],
  },
];

export const PLACES: Place[] = PLACE_GROUPS.flatMap((group) => group.places);

/**
 * The place a path belongs to: itself, or the place it sits under (a course
 * being reviewed is "Duyệt khóa học", a statement is "Thanh toán giảng viên").
 * "/quan-tri" is the parent of every path, so it only owns itself.
 */
export function placeOf(pathname: string): Place {
  const path = pathname.length > 1 ? pathname.replace(/\/+$/, "") : pathname;
  const under = PLACES.find(
    (place) => place.href !== "/quan-tri" && (path === place.href || path.startsWith(`${place.href}/`)),
  );
  return under ?? PLACES[0];
}

export function badgeCount(place: Place, summary: AdminSummary | undefined): number {
  if (!place.badge || !summary) return 0;
  return summary[place.badge];
}

/** Everything waiting, for the folded menu's button on a phone. */
export function waitingTotal(summary: AdminSummary | undefined): number {
  return summary
    ? summary.pending_courses + summary.pending_reports + summary.pending_instructor_applications
    : 0;
}

const DAY_MS = 24 * 60 * 60 * 1000;

/** From this many whole days a course has waited long, and the queue says so. */
export const LONG_WAIT_DAYS = 3;

/** Whole days between `since` and `now`; never below 0 (a clock a little ahead). */
export function waitedDays(since: string, now: Date): number {
  const elapsed = now.getTime() - new Date(since).getTime();
  return Math.max(0, Math.floor(elapsed / DAY_MS));
}

export function waitLabel(days: number): string {
  return days === 0 ? "chờ chưa tới 1 ngày" : `chờ ${days} ngày`;
}

export interface AttentionCard {
  kind: "courses" | "applications" | "reports" | "locked";
  label: string;
  count: number;
  detail: string;
  action: string;
  href: string;
  /** Informational only: nothing to decide, so it is drawn quieter. */
  quiet: boolean;
}

/**
 * The "Cần xử lý" row on the overview. The two queues are always there, with
 * a line that says nothing is waiting when nothing is: an admin opening the
 * page wants that answer too. Locked accounts are a fact, not a task.
 */
export function attentionCards(
  summary: AdminSummary,
  oldest: { title: string; days: number } | null,
): AttentionCard[] {
  return [
    {
      kind: "courses",
      label: "Khóa học chờ duyệt",
      count: summary.pending_courses,
      detail:
        summary.pending_courses === 0
          ? "Không có khóa học nào đang chờ"
          : oldest
            ? `Chờ lâu nhất: “${oldest.title}”, ${waitLabel(oldest.days)}`
            : "Chờ lâu nhất đứng đầu hàng đợi",
      action: "Mở hàng đợi",
      href: "/quan-tri/khoa-hoc",
      quiet: false,
    },
    {
      kind: "applications",
      label: "Yêu cầu làm giảng viên",
      count: summary.pending_instructor_applications,
      detail:
        summary.pending_instructor_applications === 0
          ? "Không có yêu cầu nào đang chờ"
          : "Duyệt xong, học viên vào được khu giảng dạy ngay",
      action: "Xem yêu cầu",
      href: "/quan-tri/duyet-giang-vien",
      quiet: false,
    },
    {
      kind: "reports",
      label: "Báo cáo vi phạm chờ xử lý",
      count: summary.pending_reports,
      detail:
        summary.pending_reports === 0
          ? "Không có báo cáo nào đang chờ"
          : "Một quyết định đóng mọi báo cáo về cùng nội dung",
      action: "Xử lý báo cáo",
      href: "/quan-tri/bao-cao",
      quiet: false,
    },
    {
      kind: "locked",
      label: "Tài khoản đang khóa",
      count: summary.locked_users,
      detail: "Chỉ để biết, không cần làm gì",
      action: "Xem danh sách",
      href: "/quan-tri/nguoi-dung",
      quiet: true,
    },
  ];
}
