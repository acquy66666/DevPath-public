import { apiFetch } from "./client";
import type { CourseInstructor, Page } from "./courses";

/** Mirrors `ReviewOut`. The author block is the same shape as an instructor:
 *  a name and a face, never an email. */
export interface Review {
  id: string;
  course_id: string;
  rating: number;
  comment: string | null;
  author: CourseInstructor;
  created_at: string;
  updated_at: string;
}

/**
 * Mirrors `CourseReviewsOut`: a page of reviews with the course's summary
 * attached. `rating_avg` is a string for the same reason `price` is — the
 * column is NUMERIC and a JSON number would be a double.
 */
export interface CourseReviews extends Page<Review> {
  rating_avg: string;
  rating_count: number;
}

export interface ReviewInput {
  rating: number;
  comment?: string | null;
}

/** Public: the list is part of the course page, token or no token. */
export function listCourseReviews(
  courseId: string,
  page = 1,
): Promise<CourseReviews> {
  return apiFetch<CourseReviews>(
    `/api/v1/courses/${courseId}/reviews?page=${page}`,
  );
}

/** 404 `REVIEW_NOT_FOUND` when the caller has not written one. */
export function getMyReview(
  accessToken: string,
  courseId: string,
): Promise<Review> {
  return apiFetch<Review>(`/api/v1/courses/${courseId}/reviews/me`, {
    accessToken,
  });
}

/**
 * Write or rewrite the caller's review — one address, because one person has
 * at most one review of one course.
 */
export function upsertMyReview(
  accessToken: string,
  courseId: string,
  input: ReviewInput,
): Promise<Review> {
  return apiFetch<Review>(`/api/v1/courses/${courseId}/reviews/me`, {
    method: "PUT",
    accessToken,
    body: JSON.stringify(input),
  });
}

export function deleteMyReview(
  accessToken: string,
  courseId: string,
): Promise<void> {
  return apiFetch<void>(`/api/v1/courses/${courseId}/reviews/me`, {
    method: "DELETE",
    accessToken,
  });
}
