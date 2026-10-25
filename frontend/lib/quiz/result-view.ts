/**
 * What the quiz page says about an attempt, kept out of the components so it
 * can be read and tested on its own: the level a score falls in, the words of
 * the result band, the questions that went wrong, the line above "Nộp bài",
 * the screen reader's warnings as time runs out, and the history rows.
 *
 * Type imports only: `npm test` runs this file under plain Node, which does
 * not resolve the app's extensionless imports.
 */

import type { AttemptPage, AttemptSummary, QuestionReview } from "@/lib/api/quiz";
import type { Mood } from "@/lib/mascot/moods";

/**
 * The design system's QuizResult levels (100 / ≥ 80 / ≥ 50 / below), plus the
 * clock: an attempt that reached the server after the grace window is scored
 * zero without being read, and that is not the same news as scoring zero.
 */
export const QUIZ_LEVELS = ["party", "proud", "cheer", "comfort", "expired"] as const;
export type QuizLevel = (typeof QUIZ_LEVELS)[number];

export function quizLevel(score: number, expired: boolean): QuizLevel {
  if (expired) return "expired";
  if (score >= 100) return "party";
  if (score >= 80) return "proud";
  if (score >= 50) return "cheer";
  return "comfort";
}

/** Naomi's answer to each level (bản đồ phản ứng, thiết kế UI/UX mục 5). */
export const LEVEL_MOOD: Record<QuizLevel, Mood> = {
  party: "party",
  proud: "proud",
  cheer: "cheer",
  comfort: "comfort",
  expired: "startled",
};

/**
 * Tailwind classes per level, written out whole so the build finds them: the
 * design system's `quiz-*` tokens, and `verdict-tle` for running out of time
 * (the same amber as a program that ran out of time).
 */
export const LEVEL_CLASSES: Record<QuizLevel, { text: string; soft: string; solid: string }> = {
  party: { text: "text-quiz-party", soft: "bg-quiz-party-soft", solid: "bg-quiz-party-solid" },
  proud: { text: "text-quiz-proud", soft: "bg-quiz-proud-soft", solid: "bg-quiz-proud-solid" },
  cheer: { text: "text-quiz-cheer", soft: "bg-quiz-cheer-soft", solid: "bg-quiz-cheer-solid" },
  comfort: { text: "text-quiz-comfort", soft: "bg-quiz-comfort-soft", solid: "bg-quiz-comfort-solid" },
  expired: { text: "text-verdict-tle", soft: "bg-verdict-tle-soft", solid: "bg-verdict-tle-solid" },
};

/**
 * One question of the marked paper. `unscored` is a question of an attempt the
 * clock closed: its answers never reached the server, so "bỏ trống" would be
 * a claim about what the student did that nobody can make.
 */
export type RowStatus = "correct" | "wrong" | "blank" | "unscored";

export function rowStatus(row: QuestionReview, expired: boolean): RowStatus {
  if (expired) return "unscored";
  if (row.your_answer === null) return "blank";
  return row.is_correct ? "correct" : "wrong";
}

export interface ReviewSummary {
  total: number;
  correct: number;
  /** 1-based question numbers, as the page prints them. */
  wrong: number[];
  blank: number[];
}

export function summarizeReview(review: readonly QuestionReview[], expired: boolean): ReviewSummary {
  const summary: ReviewSummary = { total: review.length, correct: 0, wrong: [], blank: [] };
  review.forEach((row, index) => {
    const status = rowStatus(row, expired);
    if (status === "correct") summary.correct += 1;
    else if (status === "wrong") summary.wrong.push(index + 1);
    else if (status === "blank") summary.blank.push(index + 1);
  });
  return summary;
}

/** Past this many, a list of numbers stops pointing anywhere: say how many. */
const LISTED = 6;

/** "Câu sai: câu 3", "Câu sai: câu 2, 3, 4 · bỏ trống: câu 5", or nothing to say. */
export function pointer(summary: ReviewSummary): string | null {
  const parts: string[] = [];
  if (summary.wrong.length > 0) {
    parts.push(
      summary.wrong.length > LISTED
        ? `${summary.wrong.length} câu sai`
        : `Câu sai: câu ${summary.wrong.join(", ")}`,
    );
  }
  if (summary.blank.length > 0) {
    const label = parts.length > 0 ? "bỏ trống" : "Bỏ trống";
    parts.push(
      summary.blank.length > LISTED
        ? `${summary.blank.length} câu bỏ trống`
        : `${label}: câu ${summary.blank.join(", ")}`,
    );
  }
  return parts.length > 0 ? parts.join(" · ") : null;
}

/** "10 phút": quizzes are written in whole minutes (the editor asks for minutes). */
export function describeLimit(seconds: number): string {
  return `${Math.max(1, Math.round(seconds / 60))} phút`;
}

export interface ResultCopy {
  /** The word on the chip: Điểm tuyệt đối, Đạt, Chưa đạt, Hết giờ. */
  chip: string;
  /** Beside the score: "4/5 câu đúng". */
  headline: string;
  /** One or two sentences: what it means and what to do next. */
  hint: string;
}

/**
 * The words of the result band. Passing goes by `passed` -- the quiz's own
 * pass mark, as the server judged it -- never by the colour: a quiz that
 * passes at 60% passes a blue 65%, and one that wants 90% does not pass a
 * green 85%.
 */
export function resultCopy(input: {
  score: number;
  passed: boolean;
  expired: boolean;
  passScore: number;
  correct: number;
  total: number;
  timeLimitS: number | null;
}): ResultCopy {
  const { score, passed, expired, passScore, correct, total, timeLimitS } = input;
  const need = `Cần ${passScore}% để đạt.`;

  if (expired) {
    const limit = timeLimitS === null ? "giờ" : describeLimit(timeLimitS);
    return {
      chip: "Hết giờ",
      headline: "Bài chưa kịp nộp",
      hint: `Bài tới máy chủ sau khi hết ${limit} nên lượt này tính 0 điểm. Đáp án đúng vẫn có bên dưới để bạn xem lại.`,
    };
  }
  if (score >= 100) {
    return {
      chip: "Điểm tuyệt đối",
      headline: `Đúng cả ${total}/${total} câu`,
      hint: "Không sót câu nào. Bài này đã được đánh dấu hoàn thành.",
    };
  }
  const headline = `${correct}/${total} câu đúng`;
  if (passed) {
    return { chip: "Đạt", headline, hint: `${need} Bài này đã được đánh dấu hoàn thành.` };
  }
  const level = quizLevel(score, false);
  const hint =
    level === "comfort"
      ? `${need} Ôn lại chương này rồi thử lần nữa — làm lại bao nhiêu lần cũng được.`
      : level === "cheer"
        ? `Gần tới rồi: cần ${passScore}% để đạt. Làm lại được ngay.`
        : `${need} Làm lại được ngay.`;
  return { chip: "Chưa đạt", headline, hint };
}

/** "0:45", "12:05", "1:02:03": a stopwatch, from start to hand-in. */
export function timeTaken(startedAt: string, submittedAt: string): string {
  const whole = Math.max(0, Math.round((Date.parse(submittedAt) - Date.parse(startedAt)) / 1000));
  const hours = Math.floor(whole / 3600);
  const minutes = Math.floor((whole % 3600) / 60);
  const seconds = String(whole % 60).padStart(2, "0");
  return hours > 0 ? `${hours}:${String(minutes).padStart(2, "0")}:${seconds}` : `${minutes}:${seconds}`;
}

/** "câu 4 và câu 5", "câu 1, câu 3 và câu 5". */
function joinVietnamese(items: string[]): string {
  if (items.length <= 1) return items.join("");
  return `${items.slice(0, -1).join(", ")} và ${items[items.length - 1]}`;
}

/**
 * The line above "Nộp bài". Handing in with blanks is allowed -- a blank is
 * marked wrong, and the student should know that before pressing, not after.
 */
export function missingLine(answers: readonly (number | null)[]): { title: string; complete: boolean } {
  const missing = answers.flatMap((answer, index) => (answer === null ? [index + 1] : []));
  if (missing.length === 0) {
    return { title: `Đã trả lời đủ ${answers.length}/${answers.length} câu`, complete: true };
  }
  const count = `Còn ${missing.length} câu chưa trả lời`;
  return {
    title: missing.length > 5 ? count : `${count}: ${joinVietnamese(missing.map((n) => `câu ${n}`))}`,
    complete: false,
  };
}

/**
 * What a screen reader hears as time runs out. The countdown itself is a
 * `timer`, which is silent by design: reading the clock out every second
 * would drown the question being read.
 */
export function timerAnnouncement(remaining: number, limit: number): string | null {
  if (remaining === 300 && limit > 300) return "Còn 5 phút";
  if (remaining === 60 && limit > 60) return "Còn 1 phút";
  if (remaining === 10) return "Còn 10 giây";
  return null;
}

export interface HistoryRow {
  id: string;
  /** "Lượt 2": counted from the first attempt. */
  number: number;
  score: number;
  passed: boolean;
  submittedAt: string;
  level: QuizLevel;
}

export interface History {
  /** Finished attempts, newest first. */
  rows: HistoryRow[];
  /** Finished attempts in all, past the first page too. */
  count: number;
  best: number | null;
  passed: boolean;
  /** The attempt still running, if there is one. */
  open: AttemptSummary | null;
}

/**
 * The history panel, from the first page of attempts (newest first). An
 * attempt still running counts towards the numbering but has no row: there
 * is no result to show for it yet.
 *
 * The list has no `expired` flag, so an attempt the clock closed reads as a
 * plain 0% here; opening it shows the truth.
 */
export function historyRows(page: AttemptPage): History {
  const rows: HistoryRow[] = [];
  let open: AttemptSummary | null = null;
  page.items.forEach((item, index) => {
    if (item.submitted_at === null || item.score === null) {
      open ??= item;
      return;
    }
    rows.push({
      id: item.id,
      number: page.total - (page.page - 1) * page.page_size - index,
      score: item.score,
      passed: item.passed === true,
      submittedAt: item.submitted_at,
      level: quizLevel(item.score, false),
    });
  });
  return {
    rows,
    // At most one attempt is ever open (a partial unique index says so).
    count: page.total - (open ? 1 : 0),
    best: rows.length > 0 ? Math.max(...rows.map((entry) => entry.score)) : null,
    passed: rows.some((entry) => entry.passed),
    open,
  };
}
