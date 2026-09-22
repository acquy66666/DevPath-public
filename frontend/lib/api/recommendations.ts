import { apiFetch } from "./client";
import type { CourseCard } from "./courses";

/** Which half of the hybrid put a card in the block. Mirrors `hybrid.SOURCE_*`. */
export type RecommendationSource = "collaborative" | "content" | "popular";

/** Mirrors `ReasonOut`: the course in the reader's history that earned a card. */
export interface RecommendationReason {
  id: string;
  title: string;
  slug: string;
}

/** Mirrors `RecommendedCourseOut`. */
export interface RecommendedCourse extends CourseCard {
  /** The model's score; 0 for a popular row, which no model scored. */
  score: number;
  /** Null for a popular row, and when the course that earned it was withdrawn. */
  because: RecommendationReason | null;
  sources: RecommendationSource[];
}

/**
 * Mirrors `RecommendationsOut`. `generated_at` is null when no batch has run
 * for this reader yet -- the items can still be there, all of them popular.
 */
export interface Recommendations {
  items: RecommendedCourse[];
  generated_at: string | null;
}

/** Mirrors `SimilarCourseOut`: a card plus its cosine with the course it is next to. */
export interface SimilarCourse extends CourseCard {
  score: number;
}

/** Mirrors `SimilarCoursesOut`. Empty means "no vector yet": draw no block. */
export interface SimilarCourses {
  items: SimilarCourse[];
}

/** "Gợi ý cho bạn" -- needs a token, because it is one person's history. */
export function getRecommendations(
  accessToken: string,
  limit: number,
): Promise<Recommendations> {
  return apiFetch<Recommendations>(`/api/v1/recommendations?limit=${limit}`, {
    accessToken,
  });
}

/** "Khóa học tương tự" -- public, so the course page can render it on the server. */
export function getSimilarCourses(
  courseId: string,
  limit: number,
): Promise<SimilarCourses> {
  return apiFetch<SimilarCourses>(`/api/v1/courses/${courseId}/similar?limit=${limit}`);
}

/** "Học tiếp theo" -- the same neighbours, less what this reader already has. */
export function getNextCourses(
  accessToken: string,
  courseId: string,
  limit: number,
): Promise<SimilarCourses> {
  return apiFetch<SimilarCourses>(`/api/v1/courses/${courseId}/next?limit=${limit}`, {
    accessToken,
  });
}
