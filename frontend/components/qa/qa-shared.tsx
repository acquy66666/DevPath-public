"use client";

import { ArrowBigUp, BadgeCheck, CheckCircle2, MessageSquare } from "lucide-react";

import { UserAvatar } from "@/components/auth/user-avatar";
import { Badge } from "@/components/ui/badge";
import type { QaAuthor, QaThread } from "@/lib/api/qa";
import { formatRelativeTime } from "@/lib/format";
import { cn } from "@/lib/utils";

/**
 * Every Q&A query sits under this key, so one invalidation after a change
 * refreshes the lesson's board, the instructor's inbox and the open thread
 * together -- they all show the same counts.
 */
export const QA_KEY = ["qa"] as const;

/** Who wrote it and when, the way both a thread and a reply open. */
export function QaByline({
  author,
  createdAt,
  instructor = false,
}: {
  author: QaAuthor;
  createdAt: string;
  /** Marks a reply written by the course's instructor. */
  instructor?: boolean;
}) {
  return (
    <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 text-body-sm">
      <UserAvatar user={author} className="size-7 text-xs" />
      <span className="truncate font-semibold">{author.full_name}</span>
      {instructor ? (
        <Badge variant="default">
          <BadgeCheck aria-hidden />
          Giảng viên
        </Badge>
      ) : null}
      <span className="shrink-0 text-muted-foreground">
        · {formatRelativeTime(createdAt)}
      </span>
    </div>
  );
}

/** The badges a thread wears on a list and at the top of its own page. */
export function QaThreadBadges({ thread }: { thread: QaThread }) {
  if (!thread.has_instructor_reply && !thread.resolved_at) return null;
  return (
    <span className="flex flex-wrap gap-1.5">
      {thread.has_instructor_reply ? (
        <Badge variant="success">
          <BadgeCheck aria-hidden />
          Giảng viên đã trả lời
        </Badge>
      ) : null}
      {thread.resolved_at ? (
        <Badge variant="outline">
          <CheckCircle2 aria-hidden />
          Đã giải quyết
        </Badge>
      ) : null}
    </span>
  );
}

/**
 * The body as one line of prose for a list row.
 *
 * The body is Markdown, and two clamped lines of it would show the fences and
 * backticks rather than the words. Only the punctuation that marks structure
 * goes; underscores stay, because in a programming course they are mostly
 * inside names like `so_chan`.
 */
export function excerpt(markdown: string): string {
  return markdown
    .replace(/```[^\n]*/g, " ")
    .replace(/\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/^\s{0,3}(#{1,6}|>)\s*/gm, "")
    .replace(/`|\*\*/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

/**
 * One question as a row: how many share it on the left, then the title, the
 * start of its body, who asked, and whether it is answered.
 *
 * The whole row is one button, so the count on the left is a figure, not a
 * second control: voting happens on the question's own page.
 */
export function QaThreadRow({
  thread,
  onOpen,
  showPlace = false,
}: {
  thread: QaThread;
  onOpen: () => void;
  /** Name the course and lesson -- in the inbox, where questions come from anywhere. */
  showPlace?: boolean;
}) {
  return (
    <li>
      <button
        type="button"
        onClick={onOpen}
        className="flex w-full items-start gap-3 rounded-lg border bg-card p-3.5 text-left transition-[background-color,box-shadow] duration-fast hover:shadow-md sm:gap-4 sm:p-4"
      >
        <span
          className={cn(
            "flex w-11 shrink-0 flex-col items-center rounded-md py-1.5 sm:w-12",
            thread.voted ? "bg-secondary text-secondary-foreground" : "bg-muted text-muted-foreground",
          )}
          title={`${thread.vote_count} người cũng có câu hỏi này`}
        >
          <ArrowBigUp className="size-4.5" aria-hidden />
          <span className="text-body-sm font-semibold tabular-nums">{thread.vote_count}</span>
          <span className="sr-only"> người cũng có câu hỏi này</span>
        </span>
        <span className="flex min-w-0 flex-1 flex-col gap-1.5">
          {showPlace ? (
            <span className="truncate text-caption text-muted-foreground">
              {thread.course.title} · {thread.lesson.title}
            </span>
          ) : null}
          <span className="text-title text-pretty break-words">{thread.title}</span>
          <span className="line-clamp-2 text-body-sm break-words text-muted-foreground">
            {excerpt(thread.body)}
          </span>
          <span className="flex flex-wrap items-center gap-x-3 gap-y-2 pt-0.5">
            <span className="inline-flex min-w-0 items-center gap-1.5 text-caption text-muted-foreground">
              <UserAvatar user={thread.author} className="size-5 text-[0.5625rem]" />
              <span className="truncate">
                {thread.author.full_name} · {formatRelativeTime(thread.created_at)}
              </span>
            </span>
            <QaThreadBadges thread={thread} />
            <span
              className="ml-auto inline-flex items-center gap-1 text-caption text-muted-foreground"
              title={`${thread.reply_count} câu trả lời`}
            >
              <MessageSquare className="size-3.5" aria-hidden />
              {thread.reply_count} trả lời
            </span>
          </span>
        </span>
      </button>
    </li>
  );
}
