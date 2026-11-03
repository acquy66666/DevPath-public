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

/** `course_approved`: an admin approved your course; it is on sale now. */
export interface CourseApprovedPayload {
  course_id: string;
  course_slug: string;
  course_title: string;
}

/**
 * `course_rejected`: an admin sent your course back.
 * `course_taken_down`: an admin took your published course off the platform.
 */
/** `instructor_tier_changed`: an admin moved you to another tier, with why. */
export interface TierChangedPayload {
  from_tier: string;
  from_rank: number;
  to_tier: string;
  to_rank: number;
  share_rate: string;
  note: string;
}

/** `instructor_application_approved`: you are an instructor now. */
export interface ApplicationApprovedPayload {
  application_id: string;
}

/** `instructor_application_rejected`: an admin turned your application down. */
export interface ApplicationRejectedPayload {
  application_id: string;
  reason: string;
}

export interface CourseDecisionPayload {
  course_id: string;
  course_title: string;
  reason: string;
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
  | (NotificationBase & { type: "qa_question"; payload: QaQuestionPayload })
  | (NotificationBase & { type: "course_approved"; payload: CourseApprovedPayload })
  | (NotificationBase & { type: "course_rejected"; payload: CourseDecisionPayload })
  | (NotificationBase & { type: "course_taken_down"; payload: CourseDecisionPayload })
  | (NotificationBase & { type: "instructor_tier_changed"; payload: TierChangedPayload })
  | (NotificationBase & {
      type: "instructor_application_approved";
      payload: ApplicationApprovedPayload;
    })
  | (NotificationBase & {
      type: "instructor_application_rejected";
      payload: ApplicationRejectedPayload;
    });

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
