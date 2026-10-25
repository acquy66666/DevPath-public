/**
 * What the achievements block says about a learner's streak, kept out of the
 * component so it can be read and tested on its own: which of four states the
 * streak is in, the words for it, the seven days of this week, Naomi's mood,
 * and whether she should react this time.
 *
 * Days are Vietnamese calendar days written "YYYY-MM-DD", as the API sends
 * `last_active_date`. Arithmetic on them goes through UTC midnight, where no
 * daylight saving or time zone can move a day.
 *
 * Type imports only: `npm test` runs this file under plain Node, which does
 * not resolve the app's extensionless imports.
 */

import type { GamificationSummary } from "@/lib/api/gamification";
import type { Mood } from "@/lib/mascot/moods";

/**
 * - `lit`: on a streak, and today already counts.
 * - `pending`: on a streak, nothing done yet today (it breaks at midnight).
 * - `lost`: the streak broke within the last week -- "vừa mất".
 * - `none`: never studied, or the last streak broke long ago.
 */
export type StreakState = "lit" | "pending" | "lost" | "none";

/** How long a broken streak is still news: Naomi stays sad for a week, then lets it go. */
export const LOST_WINDOW_DAYS = 7;

const VIETNAM_DAY = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Asia/Ho_Chi_Minh",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

/** The Vietnamese calendar day an instant falls on: the backend's idea of "today". */
export function vietnamDay(at: Date): string {
  return VIETNAM_DAY.format(at);
}

function utc(day: string): number {
  const [year, month, date] = day.split("-").map(Number);
  return Date.UTC(year, month - 1, date);
}

export function addDays(day: string, days: number): string {
  return new Date(utc(day) + days * 86_400_000).toISOString().slice(0, 10);
}

/** `to` minus `from`, in whole days. */
export function daysBetween(from: string, to: string): number {
  return Math.round((utc(to) - utc(from)) / 86_400_000);
}

/** Monday is 0, as a Vietnamese week starts. */
function weekdayIndex(day: string): number {
  return (new Date(utc(day)).getUTCDay() + 6) % 7;
}

export const WEEKDAY_SHORT = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"] as const;
const WEEKDAY_LONG = ["thứ Hai", "thứ Ba", "thứ Tư", "thứ Năm", "thứ Sáu", "thứ Bảy", "Chủ nhật"] as const;

/** "thứ Sáu 23/10". */
export function weekdayDate(day: string): string {
  const [, month, date] = day.split("-");
  return `${WEEKDAY_LONG[weekdayIndex(day)]} ${date}/${month}`;
}

export function streakState(summary: GamificationSummary, today: string): StreakState {
  if (summary.current_streak > 0) return summary.active_today ? "lit" : "pending";
  const last = summary.last_active_date;
  if (last !== null && summary.longest_streak > 0 && daysBetween(last, today) <= LOST_WINDOW_DAYS) {
    return "lost";
  }
  return "none";
}

/** Naomi in the streak card: the torch while it burns, the snuffed candle just after. */
export function streakMood(state: StreakState): Mood | null {
  if (state === "lit" || state === "pending") return "fire";
  if (state === "lost") return "sad";
  // Nothing to say yet: the course list under the block draws the page's one Naomi.
  return null;
}

/** The first and last day of the current streak, or null without one. */
export function streakSpan(summary: GamificationSummary, today: string): { from: string; to: string } | null {
  if (summary.current_streak <= 0) return null;
  const to = summary.active_today ? today : addDays(today, -1);
  return { from: addDays(to, -(summary.current_streak - 1)), to };
}

/**
 * - `done`: a day of the current streak (today too, once it counts).
 * - `open`: today, not counted yet -- the day to keep the streak alive.
 * - `off`: a past day that is not part of the current streak. Not "missed":
 *   the API only knows the current streak, not what came before it.
 * - `later`: still ahead this week.
 */
export type DayState = "done" | "open" | "off" | "later";

export type DayCell = {
  day: string;
  label: (typeof WEEKDAY_SHORT)[number];
  state: DayState;
  today: boolean;
};

/** Monday to Sunday of the week `today` is in, each day placed against the streak. */
export function weekStrip(summary: GamificationSummary, today: string): DayCell[] {
  const monday = addDays(today, -weekdayIndex(today));
  const span = streakSpan(summary, today);
  return WEEKDAY_SHORT.map((label, index) => {
    const day = addDays(monday, index);
    const inStreak = span !== null && day >= span.from && day <= span.to;
    const isToday = day === today;
    let state: DayState;
    if (day > today) state = "later";
    else if (inStreak) state = "done";
    else if (isToday) state = "open";
    else state = "off";
    return { day, label, state, today: isToday };
  });
}

/** The week strip in words, for a screen reader: it is drawn as dots. */
export function streakSentence(summary: GamificationSummary, today: string): string | null {
  const span = streakSpan(summary, today);
  if (span === null) return null;
  const end = span.to === today ? "hôm nay" : "hôm qua";
  if (span.from === span.to) return `Chuỗi 1 ngày: ${end}.`;
  return `Chuỗi ${summary.current_streak} ngày: từ ${weekdayDate(span.from)} đến ${end}.`;
}

export type StreakCopy = {
  /** The big line: "7 ngày", or "Chuỗi đã dừng". */
  value: string;
  /** Under it. */
  note: string;
  /** A sentence of its own under the head of the card, for a broken streak. */
  detail: string | null;
};

export function streakCopy(summary: GamificationSummary, state: StreakState): StreakCopy {
  const days = `${summary.current_streak} ngày`;
  switch (state) {
    case "lit":
      return { value: days, note: "Hôm nay đã được tính", detail: null };
    case "pending":
      return { value: days, note: "Học một bài hôm nay để giữ chuỗi", detail: null };
    case "lost":
      return {
        value: "Chuỗi đã dừng",
        note: `Ngày học gần nhất là ${weekdayDate(summary.last_active_date as string)}.`,
        detail: `Học một bài hôm nay để bắt đầu chuỗi mới. Chuỗi dài nhất của bạn là ${summary.longest_streak} ngày.`,
      };
    case "none":
      return { value: "0 ngày", note: "Hoàn thành một bài học để bắt đầu chuỗi.", detail: null };
  }
}

/** What this browser last reacted to, so Naomi reacts once per streak event. */
export type StreakSeen = {
  /** The last day the torch was lit for. */
  lit?: string;
  /** The last active day of the last broken streak Naomi was sad about. */
  lost?: string;
};

/**
 * Whether Naomi reacts this time, and what to remember. She lights the torch
 * the first time the page is seen after today joined the streak, and is sad
 * the first time a broken streak is seen. A streak still waiting for today,
 * or one already reacted to, is a still picture.
 */
export function streakReaction(
  summary: GamificationSummary,
  state: StreakState,
  seen: StreakSeen,
): { event: string | null; seen: StreakSeen } {
  const day = summary.last_active_date;
  if (day === null) return { event: null, seen };
  if (state === "lit" && seen.lit !== day) return { event: `lit:${day}`, seen: { ...seen, lit: day } };
  if (state === "lost" && seen.lost !== day) return { event: `lost:${day}`, seen: { ...seen, lost: day } };
  return { event: null, seen };
}
