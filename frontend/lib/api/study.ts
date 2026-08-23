import { apiFetch } from "./client";

/** Mirrors `NoteOut`. */
export interface Note {
  id: string;
  lesson_id: string;
  /** The second of the video this is about. 0 on a lesson with no timeline. */
  timestamp_s: number;
  content: string;
  created_at: string;
  updated_at: string;
}

export interface NoteInput {
  content: string;
  timestamp_s?: number;
}

export function listNotes(accessToken: string, lessonId: string): Promise<Note[]> {
  return apiFetch<Note[]>(`/api/v1/lessons/${lessonId}/notes`, { accessToken });
}

export function createNote(
  accessToken: string,
  lessonId: string,
  input: NoteInput,
): Promise<Note> {
  return apiFetch<Note>(`/api/v1/lessons/${lessonId}/notes`, {
    method: "POST",
    accessToken,
    body: JSON.stringify(input),
  });
}

export function updateNote(
  accessToken: string,
  noteId: string,
  input: NoteInput,
): Promise<Note> {
  return apiFetch<Note>(`/api/v1/notes/${noteId}`, {
    method: "PATCH",
    accessToken,
    body: JSON.stringify(input),
  });
}

export function deleteNote(accessToken: string, noteId: string): Promise<void> {
  return apiFetch<void>(`/api/v1/notes/${noteId}`, {
    method: "DELETE",
    accessToken,
  });
}

/**
 * Flag or unflag a lesson.
 *
 * Both directions are idempotent on the server, so the button never has to ask
 * what the current state is before acting on it.
 */
export function setBookmark(
  accessToken: string,
  lessonId: string,
  bookmarked: boolean,
): Promise<void> {
  return apiFetch<void>(`/api/v1/lessons/${lessonId}/bookmark`, {
    method: bookmarked ? "PUT" : "DELETE",
    accessToken,
  });
}

/** The flagged lessons of one course, for the table of contents. */
export function listBookmarks(
  accessToken: string,
  courseId: string,
): Promise<{ lesson_ids: string[] }> {
  return apiFetch<{ lesson_ids: string[] }>(
    `/api/v1/courses/${courseId}/bookmarks`,
    { accessToken },
  );
}
