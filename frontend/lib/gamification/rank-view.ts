/**
 * What the leaderboard says about where the reader stands, kept out of the
 * component so it can be read and tested on its own: the line under the
 * tabs, the "you" card's words, how far the reader climbed since they last
 * looked, and which rows stand on the podium.
 *
 * Ranks are competition ranks: equal XP, equal rank, and the next rank skips
 * (1, 1, 3). Reaching someone's XP is reaching their rank.
 *
 * Type imports only: `npm test` runs this file under plain Node, which does
 * not resolve the app's extensionless imports.
 */

import type { Leaderboard, LeaderboardEntry, LeaderboardPeriod } from "@/lib/api/leaderboard";

export const PERIODS: { value: LeaderboardPeriod; tab: string; phrase: string }[] = [
  { value: "week", tab: "Tuần này", phrase: "tuần này" },
  { value: "month", tab: "Tháng này", phrase: "tháng này" },
  { value: "all", tab: "Mọi thời gian", phrase: "từ trước tới nay" },
];

export function periodPhrase(period: LeaderboardPeriod): string {
  return PERIODS.find((item) => item.value === period)?.phrase ?? "";
}

const XP = new Intl.NumberFormat("vi-VN");

/** "1.250 XP": the design system's thousands dot. */
export function formatXp(xp: number): string {
  return `${XP.format(xp)} XP`;
}

/** "2026-09-28" → "28/09". A date, not an instant: no time zone to get wrong. */
function dayMonth(iso: string): string {
  const [, month, day] = iso.split("-");
  return `${day}/${month}`;
}

/** The line under the tabs: which days count, and how many people are on the board. */
export function periodCaption(board: Leaderboard): string {
  let when = "Tính cả mọi XP từ trước tới nay";
  if (board.period === "week" && board.starts_on && board.ends_on) {
    when = `Từ thứ Hai ${dayMonth(board.starts_on)} đến Chủ nhật ${dayMonth(board.ends_on)}`;
  } else if (board.period === "month" && board.starts_on) {
    const [year, month] = board.starts_on.split("-");
    when = `Tháng ${Number(month)}/${year}`;
  }
  return board.total > 0 ? `${when} · ${board.total} người có XP` : when;
}

export type Standing = {
  headline: string;
  /** "140 XP tuần này · 13 người trên bảng". Null when the reader is not on the board. */
  stats: string | null;
  /** How far ahead, or how much more to reach the next rank. Null when the rows that answer it are on another page. */
  gap: string | null;
};

/** The "you" card's words. */
export function standing(board: Leaderboard): Standing {
  const phrase = periodPhrase(board.period);
  const me = board.me;
  if (me === null) {
    return { headline: `Bạn chưa có XP ${phrase}`, stats: null, gap: null };
  }
  const stats = `${formatXp(me.xp)} ${phrase} · ${board.total} người trên bảng`;
  const others = board.items.filter((entry) => !entry.is_me);

  if (me.rank === 1) {
    const tied = others.filter((entry) => entry.rank === 1);
    if (tied.length > 0) {
      const with_ = tied.length === 1 ? tied[0].user.full_name : `${tied.length} người khác`;
      return { headline: `Bạn đồng hạng 1 ${phrase}`, stats, gap: `Cùng hạng với ${with_}` };
    }
    const next = others.find((entry) => entry.rank > 1);
    return {
      headline: `Bạn đang dẫn đầu ${phrase}`,
      stats,
      gap: next ? `Hơn hạng ${next.rank} là ${formatXp(me.xp - next.xp)}` : null,
    };
  }

  // The rank just above the reader's: the nearest one they can reach.
  const above = others.filter((entry) => entry.rank < me.rank).at(-1);
  return {
    headline: `Bạn đứng hạng ${me.rank} ${phrase}`,
    stats,
    gap: above ? `Cần thêm ${formatXp(above.xp - me.xp)} để lên hạng ${above.rank}` : null,
  };
}

/** How many places the reader climbed since this browser last saw this board; 0 for none or unknown. */
export function rankRise(previous: number | null, current: number | null): number {
  if (previous === null || current === null || !Number.isFinite(previous)) return 0;
  return Math.max(0, previous - current);
}

export function riseLine(places: number): string {
  return `Lên ${places} hạng từ lần trước bạn xem`;
}

/**
 * The first page's top three stand on a podium; every other row is a line of
 * the list. Fewer than three people, or any later page, and there is no
 * podium at all: a podium with an empty step reads as something missing.
 */
export function splitPodium(board: Leaderboard): { podium: LeaderboardEntry[]; rest: LeaderboardEntry[] } {
  if (board.page !== 1 || board.items.length < 3) return { podium: [], rest: board.items };
  return { podium: board.items.slice(0, 3), rest: board.items.slice(3) };
}

/** Left to right on the podium: second, first, third. */
export function podiumOrder<T>(podium: T[]): T[] {
  return podium.length === 3 ? [podium[1], podium[0], podium[2]] : podium;
}

export type Medal = "gold" | "silver" | "bronze";

/** By rank, not by place: two people tied at 1 both get gold. */
export function medalFor(rank: number): Medal | null {
  if (rank === 1) return "gold";
  if (rank === 2) return "silver";
  if (rank === 3) return "bronze";
  return null;
}
