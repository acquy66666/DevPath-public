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
