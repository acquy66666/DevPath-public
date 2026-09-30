import { apiFetch } from "./client";

export type ReportTargetType = "course" | "review" | "qa_thread" | "qa_reply";
export type ReportReason = "spam" | "offensive" | "copyright" | "misleading" | "other";

/** In the order the form lists them. `other` asks for words. */
export const REPORT_REASONS: { value: ReportReason; label: string; hint: string }[] = [
  { value: "spam", label: "Spam, quảng cáo", hint: "Rao vặt, link lạ, nội dung lặp đi lặp lại" },
  { value: "offensive", label: "Xúc phạm, quấy rối", hint: "Ngôn từ thô tục, công kích cá nhân" },
  { value: "copyright", label: "Vi phạm bản quyền", hint: "Sao chép nội dung của người khác" },
  { value: "misleading", label: "Sai sự thật, gây hiểu lầm", hint: "Thông tin sai, quảng cáo quá sự thật" },
  { value: "other", label: "Lý do khác", hint: "Mô tả vấn đề bên dưới" },
];

export const REPORT_REASON_LABELS: Record<ReportReason, string> = Object.fromEntries(
  REPORT_REASONS.map((reason) => [reason.value, reason.label]),
) as Record<ReportReason, string>;

export const REPORT_DETAILS_MAX_LENGTH = 1000;

/** Mirrors `ReportOut`: the reporter's receipt. */
export interface Report {
  id: string;
  target_type: ReportTargetType;
  target_id: string;
  reason: ReportReason;
  details: string | null;
  status: string;
  created_at: string;
}

export function createReport(
  accessToken: string,
  body: {
    target_type: ReportTargetType;
    target_id: string;
    reason: ReportReason;
    details: string | null;
  },
): Promise<Report> {
  return apiFetch<Report>("/api/v1/reports", {
    method: "POST",
    accessToken,
    body: JSON.stringify(body),
  });
}
