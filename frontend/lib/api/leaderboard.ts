import { apiFetch } from "./client";

export type LeaderboardPeriod = "week" | "month" | "all";

/** Mirrors `LeaderboardEntryOut`. A name and a face, never an email. */
export interface LeaderboardEntry {
  /** Competition ranking: equal XP, equal rank, and the next rank skips. */
  rank: number;
  user: { id: string; full_name: string; avatar_url: string | null };
  xp: number;
  is_me: boolean;
}

/** Mirrors `LeaderboardOut`. */
export interface Leaderboard {
  period: LeaderboardPeriod;
  /** First and last day of the period in Vietnam; null for all time. */
  starts_on: string | null;
  ends_on: string | null;
  items: LeaderboardEntry[];
  total: number;
  page: number;
  page_size: number;
  /** The reader's own place, on this page or not; null with no XP this period. */
  me: { rank: number; xp: number } | null;
}

export function getLeaderboard(
  accessToken: string,
  period: LeaderboardPeriod,
  page = 1,
): Promise<Leaderboard> {
  return apiFetch<Leaderboard>(`/api/v1/leaderboard?period=${period}&page=${page}`, {
    accessToken,
  });
}
