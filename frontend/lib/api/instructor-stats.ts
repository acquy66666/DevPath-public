import { apiFetch } from "./client";
import type { CourseStatus, Page } from "./courses";

/**
 * The instructor's dashboard. Types mirror
 * `backend/app/schemas/instructor_stats.py`.
 *
 * No money anywhere (since 20/10/2026): revenue and sales are the admin's.
 * Rates are plain numbers between 0 and 1, and `null` when there is nobody to
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
  enrollments: number;
  /** People whose first course with this instructor began in the period. */
  new_students: number;
  /** Distinct learners with a trace on these courses in the period. */
  active_learners: number;
  lessons_completed: number;
  completions: number;
  reviews: number;
  review_avg: number | null;
  questions: number;
  wishlist_adds: number;
}

export interface StatsPoint {
  /** First day of the bucket (a day, or the first of a month), YYYY-MM-DD. */
  bucket: string;
  enrollments: number;
  new_students: number;
  active_learners: number;
  lessons_completed: number;
  completions: number;
  reviews: number;
  questions: number;
  wishlist_adds: number;
}

export interface InstructorOverview {
  period: StatsPeriod;
  granularity: "day" | "month";
  start: string;
  end: string;
  current: StatsTotals;
  previous: StatsTotals;
  series: StatsPoint[];
  students_total: number;
  enrollments_total: number;
  courses_published: number;
  courses_total: number;
  started_rate: number | null;
  completion_rate: number | null;
  avg_progress: number | null;
  median_days_to_complete: number | null;
  rating_avg: number | null;
  rating_count: number;
  certificates_total: number;
  open_questions: number;
}

export const VERDICTS = ["AC", "WA", "TLE", "MLE", "RE", "CE"] as const;

export interface InstructorInsights {
  period: StatsPeriod;
  start: string;
  end: string;
  learning: {
    started_rate: number | null;
    idle_rate: number | null;
    median_days_to_first_lesson: number | null;
    median_days_to_complete: number | null;
  };
  quiz: {
    attempts: number;
    learners: number;
    median_score: number | null;
    first_try_pass_rate: number | null;
    expired_rate: number | null;
  };
  code: {
    submissions: number;
    learners: number;
    solve_rate: number | null;
    median_attempts_to_ac: number | null;
    verdicts: Record<(typeof VERDICTS)[number], number>;
  };
  reviews: {
    /** "1".."5" -> count, all-time. */
    distribution: Record<string, number>;
    commented_rate: number | null;
    new_reviews: number;
    new_review_avg: number | null;
  };
  qa: {
    questions: number;
    answered_rate: number | null;
    median_first_response_hours: number | null;
    answered_within_24h_rate: number | null;
    resolved_rate: number | null;
    backlog: number;
  };
  interest: {
    wishlist_adds: number;
    wishlisted_now: number;
    wishlist_conversion_rate: number | null;
    in_carts_now: number;
  };
}

export interface StatsCourse {
  id: string;
  title: string;
  slug: string;
  status: CourseStatus;
  thumbnail_url: string | null;
  /** Taken down, still listed while people are enrolled in it. */
  is_deleted: boolean;
}

export interface CourseStats {
  course: StatsCourse;
  students: number;
  new_enrollments: number;
  completed: number;
  lessons_count: number;
  started_rate: number | null;
  completion_rate: number | null;
  avg_progress: number | null;
  rating_avg: number | null;
  rating_count: number;
  open_questions: number;
  wishlisted: number;
  quiz_first_try_pass_rate: number | null;
  code_solve_rate: number | null;
}

export interface LessonStats {
  lesson_id: string;
  section_title: string;
  title: string;
  type: "video" | "article" | "quiz" | "code_exercise";
  started: number;
  completed: number;
  completion_rate: number | null;
  avg_watched: number | null;
  quiz_first_try_pass_rate: number | null;
  code_solve_rate: number | null;
  questions: number;
  notes: number;
}

export interface CourseFunnel {
  course: StatsCourse;
  enrollments: number;
  lessons: LessonStats[];
}

export interface Tier {
  id: string;
  code: string;
  name: string;
  rank: number;
  description: string | null;
  /** The instructor's share of each sale, "0.5500". */
  share_rate: string;
}

export interface TierCriterion {
  key: string;
  label: string;
  met: boolean;
  /** Null for money-shaped criteria: only whether it is met is shown. */
  value: string | null;
  threshold: string | null;
}

export interface MyTier {
  current: Tier;
  ladder: Tier[];
  next: { tier: Tier; met: boolean; criteria: TierCriterion[] } | null;
  eligible: boolean;
  history: {
    from_tier: string | null;
    to_tier: string;
    to_rank: number;
    note: string;
    created_at: string;
  }[];
}

export function getInstructorOverview(
  accessToken: string,
  period: StatsPeriod,
): Promise<InstructorOverview> {
  return apiFetch<InstructorOverview>(`/api/v1/instructor/stats/overview?period=${period}`, {
    accessToken,
  });
}

export function getInstructorInsights(
  accessToken: string,
  period: StatsPeriod,
): Promise<InstructorInsights> {
  return apiFetch<InstructorInsights>(`/api/v1/instructor/stats/insights?period=${period}`, {
    accessToken,
  });
}

export function listCourseStats(
  accessToken: string,
  params: { period: StatsPeriod; page?: number; pageSize?: number },
): Promise<Page<CourseStats>> {
  const search = new URLSearchParams({
    period: params.period,
    page: String(params.page ?? 1),
    page_size: String(params.pageSize ?? 10),
  });
  return apiFetch<Page<CourseStats>>(`/api/v1/instructor/stats/courses?${search}`, {
    accessToken,
  });
}

export function getCourseFunnel(accessToken: string, courseId: string): Promise<CourseFunnel> {
  return apiFetch<CourseFunnel>(`/api/v1/instructor/stats/courses/${courseId}/lessons`, {
    accessToken,
  });
}

export function getMyTier(accessToken: string): Promise<MyTier> {
  return apiFetch<MyTier>("/api/v1/instructor/tier", { accessToken });
}

export const instructorExportPath = (period: StatsPeriod) =>
  `/api/v1/instructor/stats/export.xlsx?period=${period}`;

export const funnelExportPath = (courseId: string) =>
  `/api/v1/instructor/stats/courses/${courseId}/lessons/export.xlsx`;
