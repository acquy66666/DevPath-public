// node --test lib/gamification/streak-view.test.ts  (npm test runs every *.test.ts)
//
// The streak card: its four states, the words for each, the seven days of the
// week, Naomi's mood, and when she reacts. Dates are those of the demo buyers
// on 25/10/2026 (a Sunday).
import assert from "node:assert/strict";
import { test } from "node:test";

import type { GamificationSummary } from "../api/gamification.ts";
import {
  addDays,
  daysBetween,
  streakCopy,
  streakMood,
  streakReaction,
  streakSentence,
  streakState,
  vietnamDay,
  weekStrip,
  weekdayDate,
} from "./streak-view.ts";

const TODAY = "2026-10-25";

function summary(over: Partial<GamificationSummary>): GamificationSummary {
  return {
    xp_total: 0,
    current_streak: 0,
    longest_streak: 0,
    last_active_date: null,
    active_today: false,
    ...over,
  };
}

// Người mua 08, 01, 38 on the seeded dev database, and a new account.
const LIT = summary({ xp_total: 350, current_streak: 7, longest_streak: 9, last_active_date: TODAY, active_today: true });
const PENDING = summary({ xp_total: 160, current_streak: 2, longest_streak: 2, last_active_date: "2026-10-24" });
const LOST = summary({ xp_total: 260, current_streak: 0, longest_streak: 7, last_active_date: "2026-10-23" });
const NEW = summary({});

test("the Vietnamese day, not the UTC one", () => {
  // 18:30 UTC on the 24th is already 01:30 on the 25th in Hà Nội.
  assert.equal(vietnamDay(new Date("2026-10-24T18:30:00Z")), "2026-10-25");
  assert.equal(vietnamDay(new Date("2026-10-24T16:59:00Z")), "2026-10-24");
  assert.equal(addDays("2026-10-31", 1), "2026-11-01");
  assert.equal(addDays("2026-03-01", -1), "2026-02-28");
  assert.equal(daysBetween("2026-10-23", TODAY), 2);
  assert.equal(weekdayDate("2026-10-23"), "thứ Sáu 23/10");
  assert.equal(weekdayDate("2026-10-25"), "Chủ nhật 25/10");
});

test("four states: lit, pending, lost within a week, none", () => {
  assert.equal(streakState(LIT, TODAY), "lit");
  assert.equal(streakState(PENDING, TODAY), "pending");
  assert.equal(streakState(LOST, TODAY), "lost");
  assert.equal(streakState(NEW, TODAY), "none");
  // Broken a week ago is still news; eight days ago it is not.
  assert.equal(streakState({ ...LOST, last_active_date: "2026-10-18" }, TODAY), "lost");
  assert.equal(streakState({ ...LOST, last_active_date: "2026-10-17" }, TODAY), "none");
});

test("Naomi holds the torch on a streak, the candle just after one, nothing before any", () => {
  assert.equal(streakMood("lit"), "fire");
  assert.equal(streakMood("pending"), "fire");
  assert.equal(streakMood("lost"), "sad");
  assert.equal(streakMood("none"), null);
});

test("the words of each state", () => {
  assert.deepEqual(streakCopy(LIT, "lit"), { value: "7 ngày", note: "Hôm nay đã được tính", detail: null });
  assert.equal(streakCopy(PENDING, "pending").note, "Học một bài hôm nay để giữ chuỗi");
  assert.deepEqual(streakCopy(LOST, "lost"), {
    value: "Chuỗi đã dừng",
    note: "Ngày học gần nhất là thứ Sáu 23/10.",
    detail: "Học một bài hôm nay để bắt đầu chuỗi mới. Chuỗi dài nhất của bạn là 7 ngày.",
  });
  assert.equal(streakCopy(NEW, "none").value, "0 ngày");
});

test("the week strip: Monday to Sunday, the streak lit, today open until it counts", () => {
  const lit = weekStrip(LIT, TODAY);
  assert.deepEqual(lit.map((d) => d.label), ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]);
  assert.equal(lit[0].day, "2026-10-19");
  assert.deepEqual(lit.map((d) => d.state), Array(7).fill("done"));
  assert.deepEqual(lit.map((d) => d.today), [false, false, false, false, false, false, true]);

  // Friday and Saturday done, Sunday still open, the days before not "missed".
  assert.deepEqual(weekStrip(PENDING, TODAY).map((d) => d.state), ["off", "off", "off", "off", "done", "done", "open"]);
  // A broken streak lights nothing: the API no longer knows how long it was.
  assert.deepEqual(weekStrip(LOST, TODAY).map((d) => d.state), ["off", "off", "off", "off", "off", "off", "open"]);

  // Midweek, the days ahead are drawn as ahead.
  const wednesday = weekStrip(summary({ current_streak: 3, last_active_date: "2026-10-21", active_today: true }), "2026-10-21");
  assert.deepEqual(wednesday.map((d) => d.state), ["done", "done", "done", "later", "later", "later", "later"]);
  // A streak longer than the week fills the week from Monday.
  const long = weekStrip(summary({ current_streak: 12, last_active_date: TODAY, active_today: true }), TODAY);
  assert.ok(long.every((d) => d.state === "done"));
});

test("the strip in words for a screen reader", () => {
  assert.equal(streakSentence(LIT, TODAY), "Chuỗi 7 ngày: từ thứ Hai 19/10 đến hôm nay.");
  assert.equal(streakSentence(PENDING, TODAY), "Chuỗi 2 ngày: từ thứ Sáu 23/10 đến hôm qua.");
  assert.equal(streakSentence(summary({ current_streak: 1, last_active_date: TODAY, active_today: true }), TODAY), "Chuỗi 1 ngày: hôm nay.");
  assert.equal(streakSentence(LOST, TODAY), null);
});

test("Naomi reacts once: to today joining the streak, and to a streak just broken", () => {
  const first = streakReaction(LIT, "lit", {});
  assert.equal(first.event, `lit:${TODAY}`);
  assert.deepEqual(first.seen, { lit: TODAY });
  // Back on the page the same day: a still picture.
  assert.equal(streakReaction(LIT, "lit", first.seen).event, null);
  // The next day it lights again.
  const tomorrow = { ...LIT, current_streak: 8, last_active_date: "2026-10-26" };
  assert.equal(streakReaction(tomorrow, "lit", first.seen).event, "lit:2026-10-26");

  // Waiting for today is not an event.
  assert.equal(streakReaction(PENDING, "pending", {}).event, null);

  const lost = streakReaction(LOST, "lost", { lit: "2026-10-23" });
  assert.equal(lost.event, "lost:2026-10-23");
  assert.deepEqual(lost.seen, { lit: "2026-10-23", lost: "2026-10-23" });
  assert.equal(streakReaction(LOST, "lost", lost.seen).event, null);

  assert.equal(streakReaction(NEW, "none", {}).event, null);
});
