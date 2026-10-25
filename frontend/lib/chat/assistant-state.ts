/**
 * What the course assistant is doing, as the panel's header says it: Naomi's
 * pose and the line under "Trợ giảng AI" (reaction map, design doc §5:
 * `thinking` while an answer streams, `answer` once it has sources).
 *
 * Kept apart from the panel so the rules are plain functions with tests --
 * the panel itself only feeds them what it already holds.
 */

/**
 * The words the backend looks for in an answer's first sentence to call it a
 * refusal (`_REFUSAL_MARK` in backend/app/services/chat.py). The prompt makes
 * a refusal open with "Nội dung này nằm ngoài phạm vi tài liệu của khóa học.";
 * the model sometimes puts "Xin lỗi bạn," in front of it, hence a mark rather
 * than the whole sentence. A test keeps the two files in step.
 */
export const REFUSAL_MARK = "ngoài phạm vi tài liệu";

/** Same rule as `chat.is_refusal`: the mark, in the first sentence of the first line. */
export function isRefusal(answer: string): boolean {
  const firstLine = answer.trim().split("\n", 1)[0] ?? "";
  const firstSentence = firstLine.split(/(?<=[.!?])\s/, 1)[0] ?? "";
  return firstSentence.toLowerCase().includes(REFUSAL_MARK);
}

export type AssistantPhase = "searching" | "writing" | "failed" | "stopped";

export interface AssistantSnapshot {
  /** The question on its way, or null when nothing is being asked. */
  live: { phase: AssistantPhase; sources: number } | null;
  /** The last stored answer of the open conversation, if there is one. */
  lastAnswer: { id: string; content: string; citations: number } | null;
}

export interface AssistantHeader {
  mood: "rest" | "thinking" | "answer";
  /** The line under "Trợ giảng AI". */
  status: string;
}

/**
 * Naomi's pose and the status line for one moment of the panel.
 *
 * - writing or looking things up: `thinking`;
 * - the last answer cites the course: `answer`, holding her open book;
 * - otherwise (nothing asked yet, a refusal, an answer that stopped): `rest`.
 */
export function assistantHeader({ live, lastAnswer }: AssistantSnapshot): AssistantHeader {
  if (live?.phase === "searching") {
    return { mood: "thinking", status: "Đang tra cứu tài liệu khóa học…" };
  }
  if (live?.phase === "writing") {
    return {
      mood: "thinking",
      status: live.sources > 0 ? `Đang soạn câu trả lời từ ${live.sources} bài…` : "Đang soạn câu trả lời…",
    };
  }
  if (live?.phase === "failed") return { mood: "rest", status: "Chưa trả lời được câu này" };
  if (live?.phase === "stopped") return { mood: "rest", status: "Đã dừng câu trả lời" };

  if (lastAnswer && lastAnswer.citations > 0) {
    return { mood: "answer", status: `Đã trả lời · ${lastAnswer.citations} nguồn trong khóa học` };
  }
  if (lastAnswer && isRefusal(lastAnswer.content)) {
    return { mood: "rest", status: "Câu vừa rồi nằm ngoài khóa học" };
  }
  return { mood: "rest", status: "Trả lời từ bài giảng của khóa này" };
}

/**
 * The lessons an answer is reading, as chips: the first few by name, the rest
 * as a count. A stepper three lines tall reads better than six titles wrapped
 * into a block.
 */
export function readingChips(titles: readonly string[], shown = 3): { titles: string[]; more: number } {
  return { titles: titles.slice(0, shown), more: Math.max(0, titles.length - shown) };
}
