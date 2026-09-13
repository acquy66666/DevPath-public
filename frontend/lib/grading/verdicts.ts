/**
 * The seven letters, in words a student can act on.
 *
 * `SE` is the one that matters here. It means the platform failed, not the
 * submission, and the sandbox rules are explicit that it is never charged to
 * the student — so it gets its own wording and its own colour rather than
 * being lumped in with the ways an answer can be wrong.
 */

export const VERDICT_LABELS: Record<string, string> = {
  AC: "Đúng",
  WA: "Sai kết quả",
  TLE: "Quá thời gian",
  MLE: "Quá bộ nhớ",
  RE: "Lỗi khi chạy",
  CE: "Lỗi cú pháp",
  SE: "Lỗi hệ thống",
};

/** A sentence explaining the letter, for the one result being looked at. */
export const VERDICT_HINTS: Record<string, string> = {
  AC: "Chương trình in ra đúng kết quả mong đợi ở mọi test case.",
  WA: "Chương trình chạy xong nhưng in ra khác kết quả mong đợi.",
  TLE: "Chương trình chạy quá lâu và bị dừng. Thường là vòng lặp không kết thúc, hoặc thuật toán chậm hơn mức đề bài cho phép.",
  MLE: "Chương trình dùng quá nhiều bộ nhớ và bị dừng.",
  RE: "Chương trình dừng giữa chừng vì một lỗi lúc chạy — chia cho 0, đọc quá mảng, gọi hàm không có…",
  CE: "Chương trình không chạy được vì sai cú pháp. Xem thông báo bên dưới.",
  SE: "Lỗi phía hệ thống chấm bài, không phải lỗi bài của bạn. Bài này chưa được chấm.",
};

export type VerdictTone = "pass" | "fail" | "system";

export function verdictTone(verdict: string | null): VerdictTone {
  if (verdict === "AC") return "pass";
  if (verdict === "SE") return "system";
  return "fail";
}

export function verdictLabel(verdict: string | null): string {
  if (verdict === null) return "Chưa chấm";
  return VERDICT_LABELS[verdict] ?? verdict;
}

/** Tailwind classes per tone, so the three of them are written down once. */
export const TONE_BADGE: Record<VerdictTone, string> = {
  pass: "bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200",
  fail: "bg-rose-100 text-rose-900 dark:bg-rose-950 dark:text-rose-200",
  system: "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200",
};
