import { apiFetch } from "./client";
import type { VideoAsset } from "./video";

/**
 * The curriculum, in the two shapes the backend keeps apart on purpose:
 * `LessonSummary` is the table of contents anyone may see, `Lesson` is the
 * lesson itself and carries the content.
 */

export type LessonType = "video" | "article" | "quiz" | "code_exercise";
/** Quiz is the one still missing an editor behind it; it arrives in phase 4. */
export type BuildableLessonType = "video" | "article" | "code_exercise";

export interface LessonSummary {
  id: string;
  title: string;
  type: LessonType;
  position: number;
  is_preview: boolean;
}

export interface Lesson extends LessonSummary {
  section_id: string;
  video_asset_id: string | null;
  article_content: string | null;
  created_at: string;
  updated_at: string;
  /** The video and how far its processing got. Null until one is uploaded. */
  video: VideoAsset | null;
}

export interface Section {
  id: string;
  course_id: string;
  title: string;
  position: number;
}

export interface SectionWithLessons extends Section {
  lessons: LessonSummary[];
}

export interface Curriculum {
  sections: SectionWithLessons[];
}

export function getCurriculum(
  courseId: string,
  accessToken?: string | null,
): Promise<Curriculum> {
  return apiFetch<Curriculum>(`/api/v1/courses/${courseId}/curriculum`, {
    accessToken,
  });
}

export function getLesson(
  lessonId: string,
  accessToken?: string | null,
): Promise<Lesson> {
  return apiFetch<Lesson>(`/api/v1/lessons/${lessonId}`, { accessToken });
}

// --- Sections --------------------------------------------------------------

export function createSection(
  accessToken: string,
  courseId: string,
  title: string,
): Promise<Section> {
  return apiFetch<Section>(`/api/v1/courses/${courseId}/sections`, {
    method: "POST",
    accessToken,
    body: JSON.stringify({ title }),
  });
}

export function updateSection(
  accessToken: string,
  sectionId: string,
  title: string,
): Promise<Section> {
  return apiFetch<Section>(`/api/v1/sections/${sectionId}`, {
    method: "PATCH",
    accessToken,
    body: JSON.stringify({ title }),
  });
}

export function deleteSection(accessToken: string, sectionId: string): Promise<void> {
  return apiFetch<void>(`/api/v1/sections/${sectionId}`, {
    method: "DELETE",
    accessToken,
  });
}

/**
 * The order of *every* section of the course, as it looks after the drag.
 *
 * The whole arrangement rather than a move instruction: the browser already
 * knows what the list became, and one request cannot leave it half-applied.
 */
export function reorderSections(
  accessToken: string,
  courseId: string,
  sectionIds: string[],
): Promise<Section[]> {
  return apiFetch<Section[]>(`/api/v1/courses/${courseId}/sections/order`, {
    method: "PUT",
    accessToken,
    body: JSON.stringify({ section_ids: sectionIds }),
  });
}

// --- Lessons ---------------------------------------------------------------

export interface LessonCreate {
  title: string;
  type: BuildableLessonType;
  is_preview?: boolean;
  article_content?: string | null;
}

export type LessonUpdate = Partial<
  Pick<Lesson, "title" | "is_preview" | "article_content">
>;

export function createLesson(
  accessToken: string,
  sectionId: string,
  input: LessonCreate,
): Promise<Lesson> {
  return apiFetch<Lesson>(`/api/v1/sections/${sectionId}/lessons`, {
    method: "POST",
    accessToken,
    body: JSON.stringify(input),
  });
}

export function updateLesson(
  accessToken: string,
  lessonId: string,
  input: LessonUpdate,
): Promise<Lesson> {
  return apiFetch<Lesson>(`/api/v1/lessons/${lessonId}`, {
    method: "PATCH",
    accessToken,
    body: JSON.stringify(input),
  });
}

export function deleteLesson(accessToken: string, lessonId: string): Promise<void> {
  return apiFetch<void>(`/api/v1/lessons/${lessonId}`, {
    method: "DELETE",
    accessToken,
  });
}

/**
 * The complete contents of one section, in order.
 *
 * Dropping a lesson from another section is the same call: a lesson listed here
 * that lives elsewhere in the course is moved in, and the section it left is
 * renumbered by the backend. That is why moving across sections needs one
 * request and not two.
 */
export function reorderLessons(
  accessToken: string,
  sectionId: string,
  lessonIds: string[],
): Promise<LessonSummary[]> {
  return apiFetch<LessonSummary[]>(`/api/v1/sections/${sectionId}/lessons/order`, {
    method: "PUT",
    accessToken,
    body: JSON.stringify({ lesson_ids: lessonIds }),
  });
}
