import { Bookmark, Check, ChevronLeft, ChevronRight, Loader2 } from "lucide-react";
import Link from "next/link";

import { Button, buttonVariants } from "@/components/ui/button";
import type { LessonSummary, LessonType } from "@/lib/api/curriculum";
import { cn } from "@/lib/utils";

/**
 * What to do with the lesson on screen: tick it, flag it to come back to,
 * move to the one before or after.
 *
 * One primary button per screen (design system): ticking the lesson while it
 * is open, "Bài tiếp theo" once it is done. A code exercise and a quiz finish
 * themselves -- an accepted submission, a passing score -- and have their own
 * primary ("Nộp bài"), so for them ticking by hand is an outline button and
 * moving on stays secondary. Ticking by hand stays possible everywhere:
 * certificates work the Udemy way.
 *
 * The neighbours are links, so the browser's back button walks the lessons,
 * and following one scrolls to the top of the next lesson.
 */
export function LessonActions({
  slug,
  type,
  finished,
  saving,
  onToggleComplete,
  flagged,
  flagging,
  onToggleFlag,
  previous,
  next,
  error,
}: {
  slug: string;
  type: LessonType;
  finished: boolean;
  saving: boolean;
  onToggleComplete: () => void;
  flagged: boolean;
  flagging: boolean;
  onToggleFlag: () => void;
  previous: LessonSummary | null;
  next: LessonSummary | null;
  error: string | null;
}) {
  const selfFinishing = type === "code_exercise" || type === "quiz";
  const nextIsMain = finished && !selfFinishing;

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <Button
          variant={finished || selfFinishing ? "outline" : "default"}
          onClick={onToggleComplete}
          disabled={saving}
          className="h-11 w-full sm:h-9 sm:w-auto"
        >
          {saving ? (
            <>
              <Loader2 className="animate-spin" aria-hidden />
              Đang lưu…
            </>
          ) : finished ? (
            "Bỏ đánh dấu hoàn thành"
          ) : (
            <>
              <Check aria-hidden />
              Đánh dấu hoàn thành
            </>
          )}
        </Button>

        <Button
          variant="outline"
          size="icon"
          onClick={onToggleFlag}
          disabled={flagging}
          aria-pressed={flagged}
          aria-label="Đánh dấu để xem lại"
          title={flagged ? "Bỏ đánh dấu xem lại" : "Đánh dấu để xem lại"}
          className={cn("size-11 sm:size-9", flagged && "text-link")}
        >
          <Bookmark className={cn(flagged && "fill-current")} aria-hidden />
        </Button>

        {previous || next ? (
          <div className="flex min-w-0 flex-1 gap-2 sm:ml-auto sm:flex-none">
            {previous ? (
              <Link
                href={`/hoc/${slug}?bai=${previous.id}`}
                title={previous.title}
                aria-label={`Bài trước: ${previous.title}`}
                className={cn(
                  buttonVariants({ variant: "outline" }),
                  "h-11 flex-1 px-3 sm:h-9 sm:flex-none sm:border-transparent sm:bg-transparent sm:shadow-none",
                )}
              >
                <ChevronLeft aria-hidden />
                Bài trước
              </Link>
            ) : null}
            {next ? (
              <Link
                href={`/hoc/${slug}?bai=${next.id}`}
                title={next.title}
                aria-label={`Bài tiếp theo: ${next.title}`}
                className={cn(
                  buttonVariants({ variant: nextIsMain ? "default" : "secondary" }),
                  "h-11 flex-1 pr-3 sm:h-9 sm:flex-none",
                )}
              >
                Bài tiếp theo
                <ChevronRight aria-hidden />
              </Link>
            ) : null}
          </div>
        ) : null}
      </div>

      {error ? (
        <p className="text-body-sm text-destructive-text">{error}</p>
      ) : selfFinishing && !finished ? (
        <p className="text-caption text-muted-foreground">
          {type === "code_exercise"
            ? "Bài code tự hoàn thành khi bạn nộp đúng mọi test."
            : "Quiz tự hoàn thành khi bạn làm đạt."}
        </p>
      ) : null}
    </div>
  );
}
