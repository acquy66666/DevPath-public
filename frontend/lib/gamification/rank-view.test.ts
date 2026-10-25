// node --test lib/gamification/rank-view.test.ts  (npm test runs every *.test.ts)
//
// The leaderboard's words about the reader: the caption, the "you" card,
// the climb since the last visit, and the podium. Boards are the dev
// database's on 25/10/2026, read as Người mua 08.
import assert from "node:assert/strict";
import { test } from "node:test";

import type { Leaderboard, LeaderboardEntry } from "../api/leaderboard.ts";
import {
  formatXp,
  medalFor,
  periodCaption,
  podiumOrder,
  rankRise,
  riseLine,
  splitPodium,
  standing,
} from "./rank-view.ts";

function entry(rank: number, name: string, xp: number, isMe = false): LeaderboardEntry {
  return { rank, user: { id: name, full_name: name, avatar_url: null }, xp, is_me: isMe };
}

function board(over: Partial<Leaderboard>): Leaderboard {
  return {
    period: "week",
    starts_on: "2026-10-19",
    ends_on: "2026-10-25",
    items: [],
    total: 0,
    page: 1,
    page_size: 20,
    me: null,
    ...over,
  };
}

const WEEK = board({
  items: [entry(1, "Người mua 08", 140, true), entry(2, "Người mua 31", 130), entry(3, "Người mua 38", 120), entry(4, "Người mua 06", 110)],
  total: 13,
  me: { rank: 1, xp: 140 },
});

const MONTH = board({
  period: "month",
  starts_on: "2026-10-01",
  ends_on: "2026-10-31",
  items: [entry(1, "Người mua 06", 420), entry(2, "Người mua 11", 240), entry(3, "Người mua 38", 160), entry(4, "Người mua 08", 140, true)],
  total: 24,
  me: { rank: 4, xp: 140 },
});

const ALL = board({
  period: "all",
  starts_on: null,
  ends_on: null,
  items: [entry(1, "Người mua 06", 420), entry(1, "Người mua 09", 420), entry(3, "Người mua 20", 350), entry(3, "Người mua 08", 350, true)],
  total: 40,
  me: { rank: 3, xp: 350 },
});

test("numbers the Vietnamese way", () => {
  assert.equal(formatXp(1250), "1.250 XP");
  assert.equal(formatXp(0), "0 XP");
});

test("the caption says which days count and how many people are on the board", () => {
  assert.equal(periodCaption(WEEK), "Từ thứ Hai 19/10 đến Chủ nhật 25/10 · 13 người có XP");
  assert.equal(periodCaption(MONTH), "Tháng 10/2026 · 24 người có XP");
  assert.equal(periodCaption(ALL), "Tính cả mọi XP từ trước tới nay · 40 người có XP");
  assert.equal(periodCaption(board({})), "Từ thứ Hai 19/10 đến Chủ nhật 25/10");
});

test("the you card: leading, behind, tied, not on the board", () => {
  assert.deepEqual(standing(WEEK), {
    headline: "Bạn đang dẫn đầu tuần này",
    stats: "140 XP tuần này · 13 người trên bảng",
    gap: "Hơn hạng 2 là 10 XP",
  });
  // Reaching 160 XP is reaching rank 3: equal XP, equal rank.
  assert.deepEqual(standing(MONTH), {
    headline: "Bạn đứng hạng 4 tháng này",
    stats: "140 XP tháng này · 24 người trên bảng",
    gap: "Cần thêm 20 XP để lên hạng 3",
  });
  // Tied at 3 with Người mua 20: the rank above is 1, at 420.
  assert.equal(standing(ALL).gap, "Cần thêm 70 XP để lên hạng 1");
  const tiedFirst = board({ period: "all", items: [entry(1, "Người mua 06", 420), entry(1, "Người mua 09", 420, true)], total: 40, me: { rank: 1, xp: 420 } });
  assert.deepEqual(standing(tiedFirst), {
    headline: "Bạn đồng hạng 1 từ trước tới nay",
    stats: "420 XP từ trước tới nay · 40 người trên bảng",
    gap: "Cùng hạng với Người mua 06",
  });
  assert.deepEqual(standing(board({ total: 13 })), { headline: "Bạn chưa có XP tuần này", stats: null, gap: null });
  // The reader is on page 2 and the rank above is not on this page: no guess.
  const elsewhere = board({ items: [entry(1, "A", 500)], total: 40, me: { rank: 25, xp: 10 } });
  assert.equal(standing({ ...elsewhere, items: [] }).gap, null);
});

test("the climb since the last visit", () => {
  assert.equal(rankRise(4, 1), 3);
  assert.equal(rankRise(1, 4), 0);
  assert.equal(rankRise(null, 1), 0);
  assert.equal(rankRise(4, null), 0);
  assert.equal(rankRise(Number.NaN, 1), 0);
  assert.equal(riseLine(3), "Lên 3 hạng từ lần trước bạn xem");
});

test("the podium: the first page's top three, second-first-third, medals by rank", () => {
  const { podium, rest } = splitPodium(WEEK);
  assert.deepEqual(podium.map((e) => e.user.full_name), ["Người mua 08", "Người mua 31", "Người mua 38"]);
  assert.deepEqual(rest.map((e) => e.rank), [4]);
  assert.deepEqual(podiumOrder(podium).map((e) => e.rank), [2, 1, 3]);
  // Fewer than three, or a later page: everything is a list row.
  assert.deepEqual(splitPodium(board({ items: [entry(1, "A", 10), entry(2, "B", 5)] })).podium, []);
  assert.deepEqual(splitPodium({ ...MONTH, page: 2 }).podium, []);
  // Ties: two golds.
  assert.deepEqual(splitPodium(ALL).podium.map((e) => medalFor(e.rank)), ["gold", "gold", "bronze"]);
  assert.equal(medalFor(4), null);
});
