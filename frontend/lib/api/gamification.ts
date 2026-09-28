import { apiFetch } from "./client";
import type { Page } from "./courses";

/** Mirrors `GamificationSummaryOut`. Always the caller's own. */
export interface GamificationSummary {
  xp_total: number;
  /** Already zero once a whole day went by with nothing done. */
  current_streak: number;
  longest_streak: number;
  /** A calendar day in Vietnam, "YYYY-MM-DD". */
  last_active_date: string | null;
  active_today: boolean;
}

export type XpReason = "lesson_completed" | "quiz_passed" | "exercise_solved";

/** Mirrors `XpEventOut`. `lesson`/`course` are null once the lesson is gone. */
export interface XpEvent {
  id: string;
  amount: number;
  reason: XpReason;
  created_at: string;
  lesson: { id: string; title: string } | null;
  course: { id: string; title: string; slug: string } | null;
}

export function getMyGamification(accessToken: string): Promise<GamificationSummary> {
  return apiFetch<GamificationSummary>("/api/v1/users/me/gamification", {
    accessToken,
  });
}

export function listMyXpEvents(
  accessToken: string,
  page = 1,
  pageSize = 5,
): Promise<Page<XpEvent>> {
  return apiFetch<Page<XpEvent>>(
    `/api/v1/users/me/xp-events?page=${page}&page_size=${pageSize}`,
    { accessToken },
  );
}
