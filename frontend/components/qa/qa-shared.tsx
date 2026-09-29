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
    <div className="flex min-w-0 items-center gap-2 text-sm">
      <UserAvatar user={author} className="size-7 text-xs" />
      <span className="truncate font-medium">{author.full_name}</span>
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
        <Badge variant="secondary" className="text-emerald-700 dark:text-emerald-400">
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

/** Votes and replies, as numbers beside a list row. */
export function QaCounts({ thread, className }: { thread: QaThread; className?: string }) {
  return (
    <span className={cn("flex items-center gap-3 text-xs text-muted-foreground", className)}>
      <span
        className={cn("inline-flex items-center gap-0.5", thread.voted && "text-primary")}
        title={`${thread.vote_count} người cũng có câu hỏi này`}
      >
        <ArrowBigUp className="size-4" aria-hidden />
        {thread.vote_count}
        <span className="sr-only"> lượt bình chọn</span>
      </span>
      <span className="inline-flex items-center gap-1" title={`${thread.reply_count} câu trả lời`}>
        <MessageSquare className="size-3.5" aria-hidden />
        {thread.reply_count}
        <span className="sr-only"> câu trả lời</span>
      </span>
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

/** One question as a row: title, the start of its body, and its numbers. */
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
        className="w-full space-y-1.5 rounded-lg border p-3 text-left transition-colors hover:bg-muted/50 focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
      >
        {showPlace ? (
          <p className="truncate text-xs text-muted-foreground">
            {thread.course.title} · {thread.lesson.title}
          </p>
        ) : null}
        <p className="font-medium text-pretty break-words">{thread.title}</p>
        <p className="line-clamp-2 text-sm break-words text-muted-foreground">
          {excerpt(thread.body)}
        </p>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="text-xs text-muted-foreground">
            {thread.author.full_name} · {formatRelativeTime(thread.created_at)}
          </span>
          <span className="flex flex-wrap items-center gap-2">
            <QaThreadBadges thread={thread} />
            <QaCounts thread={thread} />
          </span>
        </div>
      </button>
    </li>
  );
}
