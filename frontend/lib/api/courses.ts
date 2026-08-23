import type { Category } from "./categories";
import { apiFetch } from "./client";

export type CourseStatus = "draft" | "pending_review" | "published" | "rejected";
export type CourseLevel = "beginner" | "intermediate" | "advanced";

/**
 * Mirrors `CourseOut`. `price` is a string, not a number: the backend column is
 * NUMERIC(12,2) and JSON numbers are IEEE doubles -- money that survives a
 * round trip has to stay text until something formats it.
 */
export interface Course {
  id: string;
  instructor_id: string;
  category_id: string;
  title: string;
  slug: string;
  subtitle: string | null;
  description: string | null;
  thumbnail_url: string | null;
  price: string;
  level: CourseLevel;
  language: string;
  status: CourseStatus;
  published_at: string | null;
  rating_avg: string;
  rating_count: number;
  students_count: number;
  duration_total_s: number;
  created_at: string;
  updated_at: string;
}

/** Mirrors `CourseInstructorOut` — a name and a face, never an email. */
export interface CourseInstructor {
  id: string;
  full_name: string;
  avatar_url: string | null;
}

/**
 * Mirrors `CourseDetailOut`: the public page's course, with the instructor and
 * the category embedded so the page renders in one round trip.
 */
export interface CourseDetail extends Course {
  instructor: CourseInstructor;
  category: Category;
}

/**
 * Mirrors `CourseCardOut`: what the catalogue draws. Deliberately narrower than
 * `Course` — no description, no status — so a page of twenty stays small.
 */
export interface CourseCard {
  id: string;
  title: string;
  slug: string;
  subtitle: string | null;
  thumbnail_url: string | null;
  price: string;
  level: CourseLevel;
  language: string;
  rating_avg: string;
  rating_count: number;
  students_count: number;
  duration_total_s: number;
  published_at: string | null;
  instructor: CourseInstructor;
  category: Category;
}

export type CatalogSort = "relevance" | "newest" | "rating";

/** Every filter the catalogue understands. Absent keys are simply not sent. */
export interface CatalogQuery {
  q?: string;
  category_id?: string;
  price_min?: string;
  price_max?: string;
  rating_min?: string;
  sort?: CatalogSort;
  page?: number;
  page_size?: number;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface CourseCreate {
  title: string;
  category_id: string;
  subtitle?: string | null;
  description?: string | null;
  price?: string;
  level?: CourseLevel;
}

/** A PATCH body: only the keys present are touched. */
export type CourseUpdate = Partial<
  Pick<
    Course,
    "title" | "category_id" | "subtitle" | "description" | "price" | "level" | "language"
  >
>;

export function listMyCourses(
  accessToken: string,
  page = 1,
): Promise<Page<Course>> {
  return apiFetch<Page<Course>>(`/api/v1/courses/me?page=${page}`, { accessToken });
}

export function getCourse(courseId: string, accessToken?: string | null): Promise<Course> {
  return apiFetch<Course>(`/api/v1/courses/${courseId}`, { accessToken });
}

export function createCourse(
  accessToken: string,
  input: CourseCreate,
): Promise<Course> {
  return apiFetch<Course>("/api/v1/courses", {
    method: "POST",
    accessToken,
    body: JSON.stringify(input),
  });
}

export function updateCourse(
  accessToken: string,
  courseId: string,
  input: CourseUpdate,
): Promise<Course> {
  return apiFetch<Course>(`/api/v1/courses/${courseId}`, {
    method: "PATCH",
    accessToken,
    body: JSON.stringify(input),
  });
}

export function deleteCourse(accessToken: string, courseId: string): Promise<void> {
  return apiFetch<void>(`/api/v1/courses/${courseId}`, {
    method: "DELETE",
    accessToken,
  });
}

/** draft | rejected → pending_review, and straight on to published while the
 * auto-approve flag is on. */
export function submitCourse(accessToken: string, courseId: string): Promise<Course> {
  return apiFetch<Course>(`/api/v1/courses/${courseId}/submit`, {
    method: "POST",
    accessToken,
  });
}

export function unpublishCourse(accessToken: string, courseId: string): Promise<Course> {
  return apiFetch<Course>(`/api/v1/courses/${courseId}/unpublish`, {
    method: "POST",
    accessToken,
  });
}

/**
 * The public course page, by the slug in its URL.
 *
 * A token is optional and only matters for a course that is not published yet:
 * its owner (and an admin) get the page, everyone else gets 404 rather than a
 * 403 that would confirm the course exists.
 */
export function getCourseBySlug(
  slug: string,
  accessToken?: string | null,
): Promise<CourseDetail> {
  return apiFetch<CourseDetail>(
    `/api/v1/courses/by-slug/${encodeURIComponent(slug)}`,
    { accessToken },
  );
}

/**
 * Turn a filter object into a query string, dropping anything empty.
 *
 * Empty keys are dropped rather than sent blank because a GET form posts every
 * field it has, and `?q=&sort=` would otherwise become part of the URL people
 * share and the crawler indexes.
 */
export function catalogSearchParams(query: CatalogQuery): URLSearchParams {
  const params = new URLSearchParams();

  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null) continue;
    const text = String(value).trim();
    if (text === "") continue;
    params.set(key, text);
  }

  return params;
}

/** The public catalogue. No token: this endpoint only ever shows published courses. */
export function listCourses(query: CatalogQuery = {}): Promise<Page<CourseCard>> {
  const params = catalogSearchParams(query);
  const suffix = params.size > 0 ? `?${params}` : "";
  return apiFetch<Page<CourseCard>>(`/api/v1/courses${suffix}`);
}
