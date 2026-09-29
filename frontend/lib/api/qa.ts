import { apiFetch } from "./client";
import type { Page } from "./courses";

/** Mirrors `QaAuthorOut`. */
export interface QaAuthor {
  id: string;
  full_name: string;
  avatar_url: string | null;
}

/** Mirrors `QaThreadOut`. */
export interface QaThread {
  id: string;
  title: string;
  body: string;
  author: QaAuthor;
  lesson: { id: string; title: string };
  course: { id: string; title: string; slug: string };
  vote_count: number;
  /** Whether the caller has voted for it. */
  voted: boolean;
  reply_count: number;
  /** The "giảng viên đã trả lời" badge. */
  has_instructor_reply: boolean;
  resolved_at: string | null;
  created_at: string;
  updated_at: string;
}

/** Mirrors `QaReplyOut`. */
export interface QaReply {
  id: string;
  thread_id: string;
  body: string;
  author: QaAuthor;
  is_instructor_reply: boolean;
  created_at: string;
  updated_at: string;
}

export type QaSort = "newest" | "top";

/** Same limits as the columns (`QA_TITLE_MAX_LENGTH`, `QA_BODY_MAX_LENGTH`). */
export const QA_TITLE_MAX_LENGTH = 200;
export const QA_BODY_MAX_LENGTH = 5000;

export function listLessonThreads(
  accessToken: string,
  lessonId: string,
  { sort, page }: { sort: QaSort; page: number },
): Promise<Page<QaThread>> {
  const params = new URLSearchParams({ sort, page: String(page) });
  return apiFetch<Page<QaThread>>(`/api/v1/lessons/${lessonId}/qa-threads?${params}`, {
    accessToken,
  });
}

export function createThread(
  accessToken: string,
  lessonId: string,
  input: { title: string; body: string },
): Promise<QaThread> {
  return apiFetch<QaThread>(`/api/v1/lessons/${lessonId}/qa-threads`, {
    method: "POST",
    accessToken,
    body: JSON.stringify(input),
  });
}

export function getThread(accessToken: string, threadId: string): Promise<QaThread> {
  return apiFetch<QaThread>(`/api/v1/qa-threads/${threadId}`, { accessToken });
}

/** A PATCH: only the keys present change. `resolved` is the "đã giải quyết" switch. */
export function updateThread(
  accessToken: string,
  threadId: string,
  input: { title?: string; body?: string; resolved?: boolean },
): Promise<QaThread> {
  return apiFetch<QaThread>(`/api/v1/qa-threads/${threadId}`, {
    method: "PATCH",
    accessToken,
    body: JSON.stringify(input),
  });
}

export function deleteThread(accessToken: string, threadId: string): Promise<void> {
  return apiFetch<void>(`/api/v1/qa-threads/${threadId}`, { method: "DELETE", accessToken });
}

/** Both directions are idempotent on the server, like a bookmark. */
export function setVote(accessToken: string, threadId: string, voted: boolean): Promise<void> {
  return apiFetch<void>(`/api/v1/qa-threads/${threadId}/vote`, {
    method: voted ? "PUT" : "DELETE",
    accessToken,
  });
}

/** Oldest first -- a conversation reads top to bottom. */
export function listReplies(
  accessToken: string,
  threadId: string,
  page: number,
): Promise<Page<QaReply>> {
  return apiFetch<Page<QaReply>>(
    `/api/v1/qa-threads/${threadId}/replies?page=${page}&page_size=50`,
    { accessToken },
  );
}

export function createReply(
  accessToken: string,
  threadId: string,
  body: string,
): Promise<QaReply> {
  return apiFetch<QaReply>(`/api/v1/qa-threads/${threadId}/replies`, {
    method: "POST",
    accessToken,
    body: JSON.stringify({ body }),
  });
}

export function deleteReply(accessToken: string, replyId: string): Promise<void> {
  return apiFetch<void>(`/api/v1/qa-replies/${replyId}`, { method: "DELETE", accessToken });
}

/** Questions across the caller's own courses, newest first. */
export function listInstructorThreads(
  accessToken: string,
  {
    courseId,
    unanswered,
    page,
  }: { courseId: string | null; unanswered: boolean; page: number },
): Promise<Page<QaThread>> {
  const params = new URLSearchParams({ page: String(page) });
  if (courseId) params.set("course_id", courseId);
  if (unanswered) params.set("unanswered", "true");
  return apiFetch<Page<QaThread>>(`/api/v1/instructor/qa-threads?${params}`, {
    accessToken,
  });
}
