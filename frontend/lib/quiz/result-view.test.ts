// node --test lib/quiz/result-view.test.ts  (npm test runs every *.test.ts)
//
// What a quiz page says about an attempt: which of the four levels (or the
// clock) it falls in, Naomi's mood and the band's colours for it, the words of
// the result band, the questions that went wrong, the line above "Nộp bài",
// the screen reader's warnings as time runs out, and the history rows.
import assert from "node:assert/strict";
import { test } from "node:test";

import type { AttemptPage, QuestionReview } from "../api/quiz.ts";
import {
  LEVEL_CLASSES,
  LEVEL_MOOD,
  QUIZ_LEVELS,
  historyRows,
  missingLine,
  pointer,
  quizLevel,
  resultCopy,
  rowStatus,
  summarizeReview,
  timeTaken,
  timerAnnouncement,
} from "./result-view.ts";

function row(yours: number | null, key = 1): QuestionReview {
  return {
    id: crypto.randomUUID(),
    position: 0,
    question: "?",
    options: ["a", "b", "c", "d"],
    your_answer: yours,
    correct_index: key,
    explanation: null,
    is_correct: yours === key,
  };
}

test("the four levels follow the design system's 100 / 80 / 50 lines", () => {
  assert.equal(quizLevel(100, false), "party");
  assert.equal(quizLevel(99, false), "proud");
  assert.equal(quizLevel(80, false), "proud");
  assert.equal(quizLevel(79, false), "cheer");
  assert.equal(quizLevel(50, false), "cheer");
  assert.equal(quizLevel(49, false), "comfort");
  assert.equal(quizLevel(0, false), "comfort");
});

test("an attempt the clock closed is its own level, whatever it scored", () => {
  assert.equal(quizLevel(0, true), "expired");
  assert.equal(quizLevel(100, true), "expired");
});

test("every level has a Naomi and a colour set from the quiz tokens", () => {
  assert.deepEqual(QUIZ_LEVELS.map((level) => LEVEL_MOOD[level]), [
    "party",
    "proud",
    "cheer",
    "comfort",
    "startled",
  ]);
  for (const level of QUIZ_LEVELS) {
    const tone = LEVEL_CLASSES[level];
    const token = level === "expired" ? "verdict-tle" : `quiz-${level}`;
    assert.equal(tone.text, `text-${token}`);
    assert.equal(tone.soft, `bg-${token}-soft`);
    assert.equal(tone.solid, `bg-${token}-solid`);
  }
});

test("a row is right, wrong, blank -- or not scored at all when the clock closed it", () => {
  assert.equal(rowStatus(row(1), false), "correct");
  assert.equal(rowStatus(row(2), false), "wrong");
  assert.equal(rowStatus(row(null), false), "blank");
  assert.equal(rowStatus(row(null), true), "unscored");
});

test("the summary numbers questions from 1, as the page does", () => {
  const summary = summarizeReview([row(1), row(1), row(3), row(1), row(null)], false);
  assert.deepEqual(summary, { total: 5, correct: 3, wrong: [3], blank: [5] });
});

test("the pointer names what went wrong, and says nothing when nothing did", () => {
  assert.equal(pointer({ total: 5, correct: 4, wrong: [3], blank: [] }), "Câu sai: câu 3");
  assert.equal(
    pointer({ total: 5, correct: 1, wrong: [2, 3, 4], blank: [5] }),
    "Câu sai: câu 2, 3, 4 · bỏ trống: câu 5",
  );
  assert.equal(pointer({ total: 5, correct: 3, wrong: [], blank: [4, 5] }), "Bỏ trống: câu 4, 5");
  assert.equal(pointer({ total: 5, correct: 5, wrong: [], blank: [] }), null);
  // A long list becomes a count: twelve numbers is not a pointer.
  assert.equal(
    pointer({ total: 20, correct: 8, wrong: [1, 2, 3, 4, 5, 6, 7], blank: [] }),
    "7 câu sai",
  );
});

test("the band's words: tuyệt đối, đạt, gần đạt, an ủi, hết giờ", () => {
  const base = { passScore: 70, total: 5, timeLimitS: 600 };

  const party = resultCopy({ ...base, score: 100, passed: true, expired: false, correct: 5 });
  assert.equal(party.chip, "Điểm tuyệt đối");
  assert.equal(party.headline, "Đúng cả 5/5 câu");

  const proud = resultCopy({ ...base, score: 80, passed: true, expired: false, correct: 4 });
  assert.equal(proud.chip, "Đạt");
  assert.equal(proud.headline, "4/5 câu đúng");
  assert.match(proud.hint, /^Cần 70% để đạt\. Bài này đã được đánh dấu hoàn thành\.$/);

  const cheer = resultCopy({ ...base, score: 60, passed: false, expired: false, correct: 3 });
  assert.equal(cheer.chip, "Chưa đạt");
  assert.match(cheer.hint, /Gần tới rồi: cần 70% để đạt\. Làm lại được ngay\./);

  const comfort = resultCopy({ ...base, score: 20, passed: false, expired: false, correct: 1 });
  assert.equal(comfort.chip, "Chưa đạt");
  assert.match(comfort.hint, /Ôn lại chương này rồi thử lần nữa/);

  const late = resultCopy({ ...base, score: 0, passed: false, expired: true, correct: 0 });
  assert.equal(late.chip, "Hết giờ");
  assert.equal(late.headline, "Bài chưa kịp nộp");
  assert.match(late.hint, /sau khi hết 10 phút nên lượt này tính 0 điểm/);
});

test("passing goes by the quiz's own line, not by the colour", () => {
  // 65% is "cheer" blue, but a quiz that passes at 60% passes it.
  const copy = resultCopy({
    passScore: 60,
    total: 20,
    timeLimitS: null,
    score: 65,
    passed: true,
    expired: false,
    correct: 13,
  });
  assert.equal(copy.chip, "Đạt");
  assert.match(copy.hint, /Cần 60% để đạt\./);
  // 85% is "proud" green, but a quiz that wants 90% has not been passed.
  const short = resultCopy({
    passScore: 90,
    total: 20,
    timeLimitS: null,
    score: 85,
    passed: false,
    expired: false,
    correct: 17,
  });
  assert.equal(short.chip, "Chưa đạt");
  assert.match(short.hint, /^Cần 90% để đạt\. Làm lại được ngay\.$/);
});

test("time taken reads like a stopwatch", () => {
  assert.equal(timeTaken("2026-10-25T09:25:25Z", "2026-10-25T09:26:10Z"), "0:45");
  assert.equal(timeTaken("2026-10-25T09:00:00Z", "2026-10-25T09:12:05Z"), "12:05");
  assert.equal(timeTaken("2026-10-25T09:00:00Z", "2026-10-25T10:02:03Z"), "1:02:03");
});

test("the line above the submit button counts what is left blank", () => {
  assert.deepEqual(missingLine([0, 1, 2, null, null]), {
    title: "Còn 2 câu chưa trả lời: câu 4 và câu 5",
    complete: false,
  });
  assert.deepEqual(missingLine([null, 1, null, 2, null]), {
    title: "Còn 3 câu chưa trả lời: câu 1, câu 3 và câu 5",
    complete: false,
  });
  assert.deepEqual(missingLine([0, null]), { title: "Còn 1 câu chưa trả lời: câu 2", complete: false });
  assert.deepEqual(missingLine([0, 1, 2]), { title: "Đã trả lời đủ 3/3 câu", complete: true });
  assert.equal(missingLine(Array(8).fill(null)).title, "Còn 8 câu chưa trả lời");
});

test("a screen reader hears the clock at five minutes, one minute and ten seconds", () => {
  assert.equal(timerAnnouncement(300, 600), "Còn 5 phút");
  assert.equal(timerAnnouncement(60, 600), "Còn 1 phút");
  assert.equal(timerAnnouncement(10, 600), "Còn 10 giây");
  assert.equal(timerAnnouncement(299, 600), null);
  // A five-minute quiz does not open with "còn 5 phút".
  assert.equal(timerAnnouncement(300, 300), null);
});

test("history rows are numbered from the first attempt, newest first", () => {
  const page: AttemptPage = {
    total: 3,
    page: 1,
    page_size: 20,
    items: [
      { id: "c", quiz_id: "q", started_at: "2026-10-25T09:30:00Z", submitted_at: null, score: null, passed: null },
      { id: "b", quiz_id: "q", started_at: "2026-10-25T09:20:00Z", submitted_at: "2026-10-25T09:26:10Z", score: 80, passed: true },
      { id: "a", quiz_id: "q", started_at: "2026-10-25T09:10:00Z", submitted_at: "2026-10-25T09:12:00Z", score: 40, passed: false },
    ],
  };
  const history = historyRows(page);
  // The open attempt counts as lượt 3 but has no row: it has no result yet.
  assert.deepEqual(
    history.rows.map((entry) => [entry.id, entry.number, entry.level]),
    [
      ["b", 2, "proud"],
      ["a", 1, "comfort"],
    ],
  );
  assert.equal(history.count, 2);
  assert.equal(history.best, 80);
  assert.equal(history.passed, true);
  assert.equal(history.open?.id, "c");
});

test("no finished attempt means no best score", () => {
  const history = historyRows({ total: 0, page: 1, page_size: 20, items: [] });
  assert.deepEqual(history, { rows: [], count: 0, best: null, passed: false, open: null });
});
