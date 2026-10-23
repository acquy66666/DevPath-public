import { apiFetch } from "./client";

/** Mirrors LessonImageUploadTicket in backend/app/schemas/lesson_images.py. */
export interface LessonImageUploadTicket {
  upload_url: string;
  storage_key: string;
  /** What the Markdown names once the PUT succeeded. */
  public_url: string;
  expires_in: number;
  /** Must be sent back verbatim as the Content-Type of the PUT: it is signed. */
  content_type: string;
}

/** Ask where to put one picture of an article. Moves no bytes. */
export function createLessonImageUpload(
  accessToken: string,
  lessonId: string,
  input: { content_type: string; size_bytes: number },
): Promise<LessonImageUploadTicket> {
  return apiFetch<LessonImageUploadTicket>(`/api/v1/lessons/${lessonId}/images`, {
    method: "POST",
    accessToken,
    body: JSON.stringify(input),
  });
}
