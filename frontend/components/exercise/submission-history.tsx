"use client";

import { History } from "lucide-react";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import type { Submission } from "@/lib/api/submissions";
import { TONE_BADGE, verdictLabel, verdictTone } from "@/lib/grading/verdicts";

/**
 * Every attempt this student has handed in, newest first.
 *
 * Trial runs are not here and that is the server's decision, not a filter
 * applied on the way in: history is the record of what was submitted, and
 * forty rehearsals would bury the four attempts that count.
 */
export function SubmissionHistory({
  submissions,
  selectedId,
  onSelect,
}: {
  submissions: Submission[];
  selectedId: string | null;
  onSelect: (submission: Submission) => void;
}) {
  if (submissions.length === 0) {
    return (
      <EmptyState
        mood="empty-notes"
        size="md"
        title="Chưa có bài nộp nào"
        description="Viết code ở trên, chạy thử với test mẫu, rồi bấm “Nộp bài”."
      />
    );
  }

  return (
    <ul className="divide-y rounded-md border">
      {submissions.map((submission) => {
        const tone = verdictTone(submission.verdict);
        const selected = submission.id === selectedId;

        return (
          <li
            key={submission.id}
            className={`flex flex-wrap items-center gap-3 p-3 text-sm ${
              selected ? "bg-muted/50" : ""
            }`}
          >
            <span
              className={`rounded px-1.5 py-0.5 text-xs font-semibold ${
                submission.status === "done"
                  ? TONE_BADGE[tone]
                  : "bg-muted text-muted-foreground"
              }`}
            >
              {submission.status === "done"
                ? verdictLabel(submission.verdict)
                : submission.status === "error"
                  ? "Lỗi hệ thống"
                  : "Đang chấm"}
            </span>

            {submission.score !== null ? (
              <span className="tabular-nums">{submission.score}/100</span>
            ) : null}

            <time
              className="text-muted-foreground"
              dateTime={submission.created_at}
            >
              {new Date(submission.created_at).toLocaleString("vi-VN")}
            </time>

            <Button
              size="sm"
              variant="ghost"
              className="ml-auto"
              onClick={() => onSelect(submission)}
            >
              <History aria-hidden />
              Xem lại
            </Button>
          </li>
        );
      })}
    </ul>
  );
}
