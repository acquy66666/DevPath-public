import { apiFetch } from "./client";
import type { CourseStatus, Page } from "./courses";

/**
 * The instructor's dashboard. Types mirror
 * `backend/app/schemas/instructor_stats.py`.
 *
 * Money arrives as strings ("280000.00"), like every NUMERIC column; the two
 * rates are plain numbers between 0 and 1, and `null` when there is nobody to
 * measure -- which the screen must show as "—", not as 0 %.
 */

export type StatsPeriod = "7d" | "30d" | "90d" | "12m";

export const STATS_PERIODS: { value: StatsPeriod; label: string; previous: string }[] = [
  { value: "7d", label: "7 ngày", previous: "7 ngày trước đó" },
  { value: "30d", label: "30 ngày", previous: "30 ngày trước đó" },
  { value: "90d", label: "90 ngày", previous: "90 ngày trước đó" },
  { value: "12m", label: "12 tháng", previous: "12 tháng trước đó" },
];

export interface StatsTotals {
  /** What buyers paid for these courses, after each line's coupon share. */
  revenue: string;
  /** Courses sold -- one order of two courses is two sales. */
  sales: number;
  enrollments: number;
  /** People whose first course with this instructor began in the period. */
  new_students: number;
}

export interface StatsPoint extends StatsTotals {
  /** First day of the bucket (a day, or the first of a month), YYYY-MM-DD. */
  bucket: string;
}

export interface InstructorOverview {
  period: StatsPeriod;
  granularity: "day" | "month";
  start: string;
  end: string;
  current: StatsTotals;
  previous: StatsTotals;
  series: StatsPoint[];
  revenue_all_time: string;
  students_total: number;
  completion_rate: number | null;
  courses_count: number;
}

export interface CourseStats {
  course: {
    id: string;
    title: string;
    slug: string;
    status: CourseStatus;
    price: string;
    thumbnail_url: string | null;
    /** Taken down, still listed while people are enrolled in it. */
    is_deleted: boolean;
  };
  students: number;
  completed: number;
  lessons_count: number;
  completion_rate: number | null;
  avg_progress: number | null;
  new_enrollments: number;
  sales: number;
  revenue: string;
  revenue_all_time: string;
}

export function getInstructorOverview(
  accessToken: string,
  period: StatsPeriod,
): Promise<InstructorOverview> {
  return apiFetch<InstructorOverview>(
    `/api/v1/instructor/stats/overview?period=${period}`,
    { accessToken },
  );
}

export function listCourseStats(
  accessToken: string,
  period: StatsPeriod,
  page: number,
): Promise<Page<CourseStats>> {
  return apiFetch<Page<CourseStats>>(
    `/api/v1/instructor/stats/courses?period=${period}&page=${page}`,
    { accessToken },
  );
}
