import type { Category } from "./categories";
import { apiFetch } from "./client";
import type { CourseLevel, CourseStatus, Page } from "./courses";
import type { StatsPeriod } from "./instructor-stats";
import type { ReportReason, ReportTargetType } from "./reports";

/** Mirrors `AdminPersonOut` — unlike every public person, with the email. */
export interface AdminPerson {
  id: string;
  full_name: string;
  email: string;
  avatar_url: string | null;
  role: "student" | "instructor" | "admin";
  locked_at: string | null;
}

export interface AdminSummary {
  pending_courses: number;
  pending_reports: number;
  locked_users: number;
}

export function getAdminSummary(accessToken: string): Promise<AdminSummary> {
  return apiFetch<AdminSummary>("/api/v1/admin/summary", { accessToken });
}

// --- The platform dashboard -----------------------------------------------

/** Mirrors `PlatformTotals`. Money is a string, like every NUMERIC column. */
export interface PlatformTotals {
  revenue: string;
  orders: number;
  enrollments: number;
  new_users: number;
  /** Distinct people who did anything in the period. */
  active_users: number;
  /** Mean daily active users over the days of the period so far. */
  avg_daily_active: number;
}

export interface PlatformPoint {
  /** First day of the bucket, YYYY-MM-DD, Vietnamese calendar. */
  bucket: string;
  revenue: string;
  orders: number;
  enrollments: number;
  new_users: number;
  /** DAU for a day; distinct people of the month for a month. */
  active_users: number;
}

export interface PlatformOverview {
  period: StatsPeriod;
  granularity: "day" | "month";
  start: string;
  end: string;
  current: PlatformTotals;
  previous: PlatformTotals;
  series: PlatformPoint[];
  active_today: number;
  revenue_all_time: string;
  users_total: number;
  courses_published: number;
  enrollments_total: number;
}

export interface HotCourse {
  id: string;
  title: string;
  slug: string;
  status: CourseStatus;
  is_deleted: boolean;
  thumbnail_url: string | null;
  price: string;
  rating_avg: string;
  students_count: number;
  instructor_name: string;
  new_enrollments: number;
  sales: number;
  revenue: string;
}

export function getPlatformOverview(
  accessToken: string,
  period: StatsPeriod,
): Promise<PlatformOverview> {
  return apiFetch<PlatformOverview>(`/api/v1/admin/stats/overview?period=${period}`, {
    accessToken,
  });
}

export function listHotCourses(
  accessToken: string,
  period: StatsPeriod,
): Promise<Page<HotCourse>> {
  return apiFetch<Page<HotCourse>>(
    `/api/v1/admin/stats/hot-courses?period=${period}&page_size=10`,
    { accessToken },
  );
}

// --- Courses ---------------------------------------------------------------

export type AdminCourseFilter = CourseStatus | "all";

/** Mirrors `AdminCourseOut`. */
export interface AdminCourse {
  id: string;
  title: string;
  slug: string;
  subtitle: string | null;
  description: string | null;
  thumbnail_url: string | null;
  price: string;
  level: CourseLevel;
  status: CourseStatus;
  rejection_reason: string | null;
  published_at: string | null;
  created_at: string;
  updated_at: string;
  duration_total_s: number;
  lessons_count: number;
  students_count: number;
  instructor: AdminPerson;
  category: Category;
}

export function listAdminCourses(
  accessToken: string,
  { status, q, page }: { status: AdminCourseFilter; q: string; page: number },
): Promise<Page<AdminCourse>> {
  const params = new URLSearchParams({ status, page: String(page), page_size: "20" });
  if (q) params.set("q", q);
  return apiFetch<Page<AdminCourse>>(`/api/v1/admin/courses?${params}`, { accessToken });
}

export function getAdminCourse(accessToken: string, courseId: string): Promise<AdminCourse> {
  return apiFetch<AdminCourse>(`/api/v1/admin/courses/${courseId}`, { accessToken });
}

export function approveCourse(accessToken: string, courseId: string): Promise<AdminCourse> {
  return apiFetch<AdminCourse>(`/api/v1/admin/courses/${courseId}/approve`, {
    method: "POST",
    accessToken,
  });
}

export function rejectCourse(
  accessToken: string,
  courseId: string,
  reason: string,
): Promise<AdminCourse> {
  return apiFetch<AdminCourse>(`/api/v1/admin/courses/${courseId}/reject`, {
    method: "POST",
    accessToken,
    body: JSON.stringify({ reason }),
  });
}

export function takeDownCourse(
  accessToken: string,
  courseId: string,
  reason: string,
): Promise<AdminCourse> {
  return apiFetch<AdminCourse>(`/api/v1/admin/courses/${courseId}/take-down`, {
    method: "POST",
    accessToken,
    body: JSON.stringify({ reason }),
  });
}

// --- Users -----------------------------------------------------------------

export type RoleFilter = "student" | "instructor" | "admin" | "all";
export type LockFilter = "locked" | "active" | "all";

/** Mirrors `AdminUserOut`. */
export interface AdminUser extends AdminPerson {
  oauth_provider: string | null;
  has_password: boolean;
  created_at: string;
  last_login_at: string | null;
  courses_count: number;
  enrollments_count: number;
}

export function listAdminUsers(
  accessToken: string,
  { q, role, lock, page }: { q: string; role: RoleFilter; lock: LockFilter; page: number },
): Promise<Page<AdminUser>> {
  const params = new URLSearchParams({ role, lock, page: String(page), page_size: "20" });
  if (q) params.set("q", q);
  return apiFetch<Page<AdminUser>>(`/api/v1/admin/users?${params}`, { accessToken });
}

export function lockUser(accessToken: string, userId: string): Promise<AdminUser> {
  return apiFetch<AdminUser>(`/api/v1/admin/users/${userId}/lock`, {
    method: "POST",
    accessToken,
  });
}

export function unlockUser(accessToken: string, userId: string): Promise<AdminUser> {
  return apiFetch<AdminUser>(`/api/v1/admin/users/${userId}/unlock`, {
    method: "POST",
    accessToken,
  });
}

// --- Reports ---------------------------------------------------------------

export type ReportStatus = "open" | "reviewing" | "resolved" | "dismissed";
export type ReportQueue = "pending" | "closed";

/** Mirrors `ReportTargetOut`: the content as it is now; `exists` false once deleted. */
export interface ReportTarget {
  exists: boolean;
  title: string | null;
  excerpt: string | null;
  rating: number | null;
  author: AdminPerson | null;
  course: { id: string; title: string; slug: string; status: CourseStatus } | null;
  lesson_id: string | null;
  thread_id: string | null;
}

/** Mirrors `AdminReportOut`. */
export interface AdminReport {
  id: string;
  target_type: ReportTargetType;
  target_id: string;
  reason: ReportReason;
  details: string | null;
  status: ReportStatus;
  created_at: string;
  reporter: AdminPerson;
  target: ReportTarget;
  pending_on_target: number;
  resolved_at: string | null;
  resolved_by: AdminPerson | null;
  resolution_note: string | null;
  content_removed: boolean;
}

export function listAdminReports(
  accessToken: string,
  {
    status,
    targetType,
    page,
  }: { status: ReportQueue; targetType: ReportTargetType | null; page: number },
): Promise<Page<AdminReport>> {
  const params = new URLSearchParams({ status, page: String(page), page_size: "20" });
  if (targetType) params.set("target_type", targetType);
  return apiFetch<Page<AdminReport>>(`/api/v1/admin/reports?${params}`, { accessToken });
}

export function startReportReview(accessToken: string, reportId: string): Promise<AdminReport> {
  return apiFetch<AdminReport>(`/api/v1/admin/reports/${reportId}/review`, {
    method: "POST",
    accessToken,
  });
}

export function resolveReport(
  accessToken: string,
  reportId: string,
  body: { note: string | null; remove_content: boolean },
): Promise<AdminReport> {
  return apiFetch<AdminReport>(`/api/v1/admin/reports/${reportId}/resolve`, {
    method: "POST",
    accessToken,
    body: JSON.stringify(body),
  });
}

export function dismissReport(
  accessToken: string,
  reportId: string,
  note: string | null,
): Promise<AdminReport> {
  return apiFetch<AdminReport>(`/api/v1/admin/reports/${reportId}/dismiss`, {
    method: "POST",
    accessToken,
    body: JSON.stringify({ note }),
  });
}

// --- Categories ------------------------------------------------------------

/** Mirrors `AdminCategoryOut`. */
export interface AdminCategory {
  id: string;
  name: string;
  slug: string;
  position: number;
  parent_id: string | null;
  /** Courses filed directly here, taken-down ones excluded. */
  courses_count: number;
}

export interface AdminCategoryTree extends AdminCategory {
  children: AdminCategory[];
}

export function listAdminCategories(accessToken: string): Promise<AdminCategoryTree[]> {
  return apiFetch<AdminCategoryTree[]>("/api/v1/admin/categories", { accessToken });
}

export function createCategory(
  accessToken: string,
  body: { name: string; parent_id: string | null },
): Promise<AdminCategory> {
  return apiFetch<AdminCategory>("/api/v1/admin/categories", {
    method: "POST",
    accessToken,
    body: JSON.stringify(body),
  });
}

/** Only the keys present are changed; `parent_id: null` moves to the top level. */
export function updateCategory(
  accessToken: string,
  categoryId: string,
  body: { name?: string; parent_id?: string | null },
): Promise<AdminCategory> {
  return apiFetch<AdminCategory>(`/api/v1/admin/categories/${categoryId}`, {
    method: "PATCH",
    accessToken,
    body: JSON.stringify(body),
  });
}

export function reorderCategories(
  accessToken: string,
  parentId: string | null,
  ids: string[],
): Promise<AdminCategoryTree[]> {
  return apiFetch<AdminCategoryTree[]>("/api/v1/admin/categories/order", {
    method: "PUT",
    accessToken,
    body: JSON.stringify({ parent_id: parentId, ids }),
  });
}

export function deleteCategory(accessToken: string, categoryId: string): Promise<void> {
  return apiFetch<void>(`/api/v1/admin/categories/${categoryId}`, {
    method: "DELETE",
    accessToken,
  });
}

// --- Coupons ---------------------------------------------------------------

export type CouponStatus = "scheduled" | "live" | "exhausted" | "ended";
export type CouponFilter = CouponStatus | "all";

/** Mirrors `AdminCouponOut`. */
export interface AdminCoupon {
  id: string;
  code: string;
  discount_type: "percent" | "fixed";
  /** A percentage, or an amount in VND -- a string like every NUMERIC. */
  value: string;
  scope: "site" | "courses";
  courses: { id: string; title: string }[];
  max_uses: number | null;
  used_count: number;
  valid_from: string;
  valid_to: string | null;
  status: CouponStatus;
  created_at: string;
}

export interface CouponInput {
  discount_type: "percent" | "fixed";
  value: string;
  scope: "site" | "courses";
  course_ids: string[];
  max_uses: number | null;
  valid_from: string | null;
  valid_to: string | null;
}

export function listAdminCoupons(
  accessToken: string,
  { status, q, page }: { status: CouponFilter; q: string; page: number },
): Promise<Page<AdminCoupon>> {
  const params = new URLSearchParams({ status, page: String(page), page_size: "20" });
  if (q) params.set("q", q);
  return apiFetch<Page<AdminCoupon>>(`/api/v1/admin/coupons?${params}`, { accessToken });
}

export function createCoupon(
  accessToken: string,
  body: CouponInput & { code: string },
): Promise<AdminCoupon> {
  return apiFetch<AdminCoupon>("/api/v1/admin/coupons", {
    method: "POST",
    accessToken,
    body: JSON.stringify(body),
  });
}

export function updateCoupon(
  accessToken: string,
  couponId: string,
  body: Partial<CouponInput>,
): Promise<AdminCoupon> {
  return apiFetch<AdminCoupon>(`/api/v1/admin/coupons/${couponId}`, {
    method: "PATCH",
    accessToken,
    body: JSON.stringify(body),
  });
}

export function endCoupon(accessToken: string, couponId: string): Promise<AdminCoupon> {
  return apiFetch<AdminCoupon>(`/api/v1/admin/coupons/${couponId}/end`, {
    method: "POST",
    accessToken,
  });
}

export function deleteCoupon(accessToken: string, couponId: string): Promise<void> {
  return apiFetch<void>(`/api/v1/admin/coupons/${couponId}`, {
    method: "DELETE",
    accessToken,
  });
}
