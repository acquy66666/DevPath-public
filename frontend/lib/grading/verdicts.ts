/**
 * The seven letters, in words a student can act on.
 *
 * `SE` is the one that matters here. It means the platform failed, not the
 * submission, and the sandbox rules are explicit that it is never charged to
 * the student — so it gets its own wording and its own colour (grey, not red)
 * rather than being lumped in with the ways an answer can be wrong.
 *
 * Colours and Naomi's mood per letter follow the design system's Verdict
 * component (docs/ui-ux/design-system/project/components/Verdict).
 */

import type { Mood } from "@/lib/mascot/moods";

export const VERDICTS = ["AC", "WA", "TLE", "MLE", "RE", "CE", "SE"] as const;
export type Verdict = (typeof VERDICTS)[number];

export const VERDICT_LABELS: Record<Verdict, string> = {
  AC: "Đúng",
  WA: "Sai kết quả",
  TLE: "Quá thời gian",
  MLE: "Quá bộ nhớ",
  RE: "Lỗi khi chạy",
  CE: "Lỗi cú pháp",
  SE: "Lỗi hệ thống",
};

/** A sentence explaining the letter, for the one result being looked at. */
export const VERDICT_HINTS: Record<Verdict, string> = {
  AC: "Chương trình in ra đúng kết quả mong đợi ở mọi test case.",
  WA: "Chương trình chạy xong nhưng in ra khác kết quả mong đợi.",
  TLE: "Chương trình chạy quá lâu và bị dừng. Thường là vòng lặp không kết thúc, hoặc thuật toán chậm hơn mức đề bài cho phép.",
  MLE: "Chương trình dùng quá nhiều bộ nhớ và bị dừng.",
  RE: "Chương trình dừng giữa chừng vì một lỗi lúc chạy — chia cho 0, đọc quá mảng, gọi hàm không có…",
  CE: "Chương trình không chạy được vì sai cú pháp. Xem thông báo bên dưới.",
  SE: "Lỗi phía hệ thống chấm bài, không phải lỗi bài của bạn. Bài này chưa được chấm.",
};

/**
 * Naomi's answer to each letter (bản đồ phản ứng, thiết kế UI/UX mục 5): AC is
 * the bug caught, WA the bug that got away, SE her "đang sửa" sign.
 */
export const VERDICT_MOOD: Record<Verdict, Mood> = {
  AC: "celebrate",
  WA: "partial",
  TLE: "sleepy",
  MLE: "stuffed",
  RE: "dizzy",
  CE: "tangled",
  SE: "sorry",
};

/**
 * Tailwind classes per letter, written out whole so the build finds them:
 * `text` for words and icons, `soft` for a background, `solid` for a dot or a
 * segment of the progress bar, `border` for the box holding a wrong answer.
 * The values are the design system's `verdict-*` tokens in app/globals.css.
 */
export const VERDICT_CLASSES: Record<Verdict, { text: string; soft: string; solid: string; border: string }> = {
  AC: { text: "text-verdict-ac", soft: "bg-verdict-ac-soft", solid: "bg-verdict-ac-solid", border: "border-verdict-ac-solid" },
  WA: { text: "text-verdict-wa", soft: "bg-verdict-wa-soft", solid: "bg-verdict-wa-solid", border: "border-verdict-wa-solid" },
  TLE: { text: "text-verdict-tle", soft: "bg-verdict-tle-soft", solid: "bg-verdict-tle-solid", border: "border-verdict-tle-solid" },
  MLE: { text: "text-verdict-mle", soft: "bg-verdict-mle-soft", solid: "bg-verdict-mle-solid", border: "border-verdict-mle-solid" },
  RE: { text: "text-verdict-re", soft: "bg-verdict-re-soft", solid: "bg-verdict-re-solid", border: "border-verdict-re-solid" },
  CE: { text: "text-verdict-ce", soft: "bg-verdict-ce-soft", solid: "bg-verdict-ce-solid", border: "border-verdict-ce-solid" },
  SE: { text: "text-verdict-se", soft: "bg-verdict-se-soft", solid: "bg-verdict-se-solid", border: "border-verdict-se-solid" },
};

/**
 * A letter the server sent, narrowed to one this page knows. Anything else —
 * a letter added to the grader before the frontend learned it — is drawn as
 * `SE`: grey and "not your fault" is the honest reading of "we cannot say".
 */
export function asVerdict(verdict: string | null): Verdict | null {
  if (verdict === null) return null;
  return (VERDICTS as readonly string[]).includes(verdict) ? (verdict as Verdict) : "SE";
}

export function verdictLabel(verdict: string | null): string {
  if (verdict === null) return "Chưa chấm";
  return VERDICT_LABELS[verdict as Verdict] ?? verdict;
}
