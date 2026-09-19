"use client";

import { Loader2, MessageSquare, Trash2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import type { ChatSession } from "@/lib/api/chat";
import { formatRelativeTime } from "@/lib/format";
import { cn } from "@/lib/utils";

/**
 * Past conversations in this course, most recently answered first.
 *
 * Deleting asks once, in place: it takes every message with it and there is
 * no way back, but a dialog over a chat panel is heavier than the decision.
 */
export function ChatHistory({
  sessions,
  currentId,
  hasMore,
  loadingMore,
  deletingId,
  onLoadMore,
  onOpen,
  onDelete,
}: {
  sessions: ChatSession[];
  currentId: string | null;
  hasMore: boolean;
  loadingMore: boolean;
  deletingId: string | null;
  onLoadMore: () => void;
  onOpen: (sessionId: string) => void;
  onDelete: (sessionId: string) => void;
}) {
  const [confirming, setConfirming] = useState<string | null>(null);

  if (sessions.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 p-6 text-center">
        <MessageSquare className="size-8 text-muted-foreground" aria-hidden />
        <p className="text-sm text-muted-foreground">
          Chưa có cuộc trò chuyện nào trong khóa học này.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-1 p-2">
      <ul className="space-y-1">
        {sessions.map((session) => (
          <li key={session.id}>
            {confirming === session.id ? (
              <div className="space-y-2 rounded-lg border border-destructive/30 bg-destructive/5 p-3">
                <p className="text-sm">Xóa cuộc trò chuyện này cùng mọi tin nhắn trong đó?</p>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant="destructive"
                    disabled={deletingId === session.id}
                    onClick={() => onDelete(session.id)}
                  >
                    {deletingId === session.id ? (
                      <Loader2 className="animate-spin" aria-hidden />
                    ) : null}
                    Xóa
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setConfirming(null)}>
                    Hủy
                  </Button>
                </div>
              </div>
            ) : (
              <div
                className={cn(
                  "group flex items-center gap-1 rounded-lg transition-colors hover:bg-muted",
                  session.id === currentId && "bg-muted",
                )}
              >
                <button
                  type="button"
                  onClick={() => onOpen(session.id)}
                  aria-current={session.id === currentId ? "true" : undefined}
                  className="min-w-0 flex-1 px-3 py-2 text-left"
                >
                  <span
                    className={cn(
                      "block truncate text-sm",
                      session.title === null && "text-muted-foreground italic",
                    )}
                  >
                    {session.title ?? "Chưa có câu hỏi nào được trả lời"}
                  </span>
                  <span className="block text-xs text-muted-foreground">
                    {formatRelativeTime(session.updated_at)}
                  </span>
                </button>
                <Button
                  size="icon-sm"
                  variant="ghost"
                  className="mr-1 opacity-60 group-hover:opacity-100 focus-visible:opacity-100"
                  aria-label={`Xóa cuộc trò chuyện “${session.title ?? "chưa đặt tên"}”`}
                  onClick={() => setConfirming(session.id)}
                >
                  <Trash2 aria-hidden />
                </Button>
              </div>
            )}
          </li>
        ))}
      </ul>

      {hasMore ? (
        <Button
          variant="ghost"
          size="sm"
          className="w-full"
          onClick={onLoadMore}
          disabled={loadingMore}
        >
          {loadingMore ? <Loader2 className="animate-spin" aria-hidden /> : null}
          Xem thêm
        </Button>
      ) : null}
    </div>
  );
}
