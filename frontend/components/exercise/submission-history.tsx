"use client";

import { History } from "lucide-react";

import { GradingChip, VerdictChip } from "@/components/exercise/verdict-chip";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import type { Submission } from "@/lib/api/submissions";
import { formatDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";

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
    <ul className="divide-y divide-border overflow-hidden rounded-lg border border-border bg-card">
      {submissions.map((submission) => {
        const selected = submission.id === selectedId;

        return (
          <li
            key={submission.id}
            aria-current={selected ? "true" : undefined}
            className={cn(
              "flex flex-wrap items-center gap-x-2 gap-y-1 py-2 pr-2 pl-3.5 sm:gap-x-3",
              selected && "bg-muted",
            )}
          >
            {submission.status === "done" ? (
              <VerdictChip verdict={submission.verdict ?? "SE"} />
            ) : submission.status === "error" ? (
              <VerdictChip verdict="SE" />
            ) : (
              <GradingChip />
            )}

            <span className="text-body-sm font-semibold tabular-nums sm:w-16">
              {submission.score === null ? "—" : `${submission.score}/100`}
            </span>

            <time
              className="text-body-sm text-muted-foreground tabular-nums max-sm:order-last max-sm:basis-full"
              dateTime={submission.created_at}
            >
              {formatDateTime(submission.created_at)}
            </time>

            {selected ? (
              <span className="ml-auto px-2.5 text-caption font-semibold text-muted-foreground">
                Đang xem
              </span>
            ) : (
              <Button size="sm" variant="ghost" className="ml-auto" onClick={() => onSelect(submission)}>
                <History aria-hidden />
                Xem lại
              </Button>
            )}
          </li>
        );
      })}
    </ul>
  );
}
