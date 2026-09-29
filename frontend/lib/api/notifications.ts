import { apiFetch } from "./client";
import type { Page } from "./courses";

/** `qa_reply`: somebody else answered a question you asked. */
export interface QaReplyPayload {
  thread_id: string;
  reply_id: string;
  lesson_id: string;
  course_id: string;
  course_slug: string;
  thread_title: string;
  replier_name: string;
  is_instructor_reply: boolean;
}

/** `qa_question`: a learner asked a question in a course you teach. */
export interface QaQuestionPayload {
  thread_id: string;
  lesson_id: string;
  course_id: string;
  course_title: string;
  lesson_title: string;
  thread_title: string;
  asker_name: string;
}

interface NotificationBase {
  id: string;
  read_at: string | null;
  created_at: string;
}

/**
 * Mirrors `NotificationOut`, narrowed by `type`.
 *
 * Only the types this build knows are listed, so a `switch` on `type` narrows
 * the payload. The backend can still learn a new kind before the page is
 * redeployed; whatever reads these keeps a `default` branch for that.
 */
export type AppNotification =
  | (NotificationBase & { type: "qa_reply"; payload: QaReplyPayload })
  | (NotificationBase & { type: "qa_question"; payload: QaQuestionPayload });

export function listNotifications(
  accessToken: string,
  { unread, page, pageSize = 20 }: { unread: boolean; page: number; pageSize?: number },
): Promise<Page<AppNotification>> {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  if (unread) params.set("unread", "true");
  return apiFetch<Page<AppNotification>>(`/api/v1/notifications?${params}`, { accessToken });
}

export function getUnreadCount(accessToken: string): Promise<{ count: number }> {
  return apiFetch<{ count: number }>("/api/v1/notifications/unread-count", { accessToken });
}

/** Idempotent: the server keeps the first time it was read. */
export function markNotificationRead(accessToken: string, id: string): Promise<void> {
  return apiFetch<void>(`/api/v1/notifications/${id}/read`, { method: "POST", accessToken });
}

export function markAllNotificationsRead(accessToken: string): Promise<{ marked: number }> {
  return apiFetch<{ marked: number }>("/api/v1/notifications/read-all", {
    method: "POST",
    accessToken,
  });
}
