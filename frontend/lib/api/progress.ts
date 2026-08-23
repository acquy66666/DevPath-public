import { apiFetch } from "./client";

/** Mirrors `LessonProgressOut`. */
export interface LessonProgress {
  lesson_id: string;
  last_position_s: number;
  completed_at: string | null;
}

/** Mirrors `CourseProgressOut`. */
export interface CourseProgress {
  enrollment_id: string;
  /** The whole course. Set when every lesson is finished, cleared when one is not. */
  completed_at: string | null;
  lesson_count: number;
  completed_count: number;
  /** Where "tiếp tục học" goes; null only for a course with no lessons. */
  resume_lesson_id: string | null;
  lessons: LessonProgress[];
}

export interface ProgressInput {
  last_position_s: number;
  /**
   * Left out by the heartbeat on purpose. Sending `false` every ten seconds
   * would un-finish a lesson the reader has already completed.
   */
  completed?: boolean;
}

export function saveProgress(
  accessToken: string,
  lessonId: string,
  input: ProgressInput,
): Promise<LessonProgress> {
  return apiFetch<LessonProgress>(`/api/v1/lessons/${lessonId}/progress`, {
    method: "PUT",
    accessToken,
    body: JSON.stringify(input),
  });
}

export function getCourseProgress(
  accessToken: string,
  courseId: string,
): Promise<CourseProgress> {
  return apiFetch<CourseProgress>(`/api/v1/courses/${courseId}/progress`, {
    accessToken,
  });
}
