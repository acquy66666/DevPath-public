"use client";

import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowBigUp,
  ArrowLeft,
  CheckCircle2,
  Loader2,
  Pencil,
  RotateCcw,
  Trash2,
} from "lucide-react";
import { useState, type FormEvent } from "react";

import { ReportButton } from "@/components/reports/report-button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Markdown } from "@/components/ui/markdown";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api/client";
import { apiErrorMessage, type MessageOverrides } from "@/lib/api/error-messages";
import {
  createReply,
  deleteReply,
  deleteThread,
  getThread,
  listReplies,
  QA_BODY_MAX_LENGTH,
  QA_TITLE_MAX_LENGTH,
  setVote,
  updateThread,
  type QaReply,
} from "@/lib/api/qa";
import { cn } from "@/lib/utils";

import { QA_KEY, QaByline, QaThreadBadges } from "./qa-shared";

export const QA_MESSAGES: MessageOverrides = {
  NOT_ENROLLED: "Hỏi đáp dành cho học viên đã đăng ký khóa học này.",
};

/**
 * One question, its answers, and the box to answer it in.
 *
 * Shared by the learning page and the instructor's inbox. What a reader may do
 * follows the server's rules -- the asker edits, the asker or the course staff
 * resolves and deletes, anybody but the asker votes -- and the buttons only
 * mirror them: a button missing here is also a 403 there.
 */
export function QaThreadView({
  threadId,
  accessToken,
  currentUserId,
  staff,
  onBack,
  backLabel = "Tất cả câu hỏi",
}: {
  threadId: string;
  accessToken: string;
  currentUserId: string | null;
  /** The course's instructor (or an admin): may resolve and delete anything here. */
  staff: boolean;
  onBack: () => void;
  backLabel?: string;
}) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState("");
  const [editing, setEditing] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const [editBody, setEditBody] = useState("");
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  const thread = useQuery({
    queryKey: [...QA_KEY, "thread", threadId],
    queryFn: () => getThread(accessToken, threadId),
  });

  const replies = useInfiniteQuery({
    queryKey: [...QA_KEY, "replies", threadId],
    queryFn: ({ pageParam }) => listReplies(accessToken, threadId, pageParam),
    initialPageParam: 1,
    getNextPageParam: (last) =>
      last.page * last.page_size < last.total ? last.page + 1 : undefined,
  });
  const allReplies = replies.data?.pages.flatMap((page) => page.items) ?? [];
  const replyTotal = replies.data?.pages[0]?.total ?? 0;

  // Every count on every list shows this thread too, so one change refreshes
  // them all rather than patching each cache by hand.
  const refresh = () => queryClient.invalidateQueries({ queryKey: QA_KEY });

  const vote = useMutation({
    mutationFn: (next: boolean) => setVote(accessToken, threadId, next),
    onSettled: refresh,
  });

  const resolve = useMutation({
    mutationFn: (next: boolean) => updateThread(accessToken, threadId, { resolved: next }),
    onSettled: refresh,
  });

  const edit = useMutation({
    mutationFn: () =>
      updateThread(accessToken, threadId, { title: editTitle.trim(), body: editBody.trim() }),
    onSuccess: () => setEditing(false),
    onSettled: refresh,
  });

  const removeThread = useMutation({
    mutationFn: () => deleteThread(accessToken, threadId),
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: [...QA_KEY, "thread", threadId] });
      refresh();
      onBack();
    },
  });

  const answer = useMutation({
    mutationFn: () => createReply(accessToken, threadId, draft.trim()),
    onSuccess: () => setDraft(""),
    onSettled: refresh,
  });

  const removeReply = useMutation({
    mutationFn: (reply: QaReply) => deleteReply(accessToken, reply.id),
    onSettled: refresh,
  });

  function submitReply(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (draft.trim() === "") return;
    answer.mutate();
  }

  const back = (
    <button
      type="button"
      onClick={onBack}
      className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
    >
      <ArrowLeft className="size-4" aria-hidden />
      {backLabel}
    </button>
  );

  if (thread.isError) {
    const gone = thread.error instanceof ApiError && thread.error.status === 404;
    return (
      <div className="space-y-3">
        {back}
        <Alert variant={gone ? "default" : "destructive"}>
          <AlertDescription>
            {gone
              ? "Câu hỏi này không còn nữa — có thể người hỏi hoặc giảng viên đã xóa."
              : apiErrorMessage(thread.error, QA_MESSAGES)}
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  if (!thread.data) {
    return (
      <div className="space-y-3">
        {back}
        <div className="h-40 animate-pulse rounded-md bg-muted/50" aria-hidden />
      </div>
    );
  }

  const data = thread.data;
  const isAuthor = data.author.id === currentUserId;
  const canModerate = isAuthor || staff;
  const failed = [vote, resolve, removeThread, removeReply].find((m) => m.isError);

  return (
    <article className="space-y-5">
      {back}

      <header className="space-y-2">
        {editing ? (
          <form
            className="space-y-2"
            onSubmit={(event) => {
              event.preventDefault();
              edit.mutate();
            }}
          >
            <Input
              value={editTitle}
              onChange={(event) => setEditTitle(event.target.value)}
              maxLength={QA_TITLE_MAX_LENGTH}
              aria-label="Tiêu đề câu hỏi"
            />
            <Textarea
              value={editBody}
              onChange={(event) => setEditBody(event.target.value)}
              maxLength={QA_BODY_MAX_LENGTH}
              rows={5}
              aria-label="Nội dung câu hỏi"
            />
            {edit.isError ? (
              <Alert variant="destructive">
                <AlertDescription>{apiErrorMessage(edit.error, QA_MESSAGES)}</AlertDescription>
              </Alert>
            ) : null}
            <div className="flex gap-2">
              <Button
                size="sm"
                type="submit"
                disabled={edit.isPending || editTitle.trim() === "" || editBody.trim() === ""}
              >
                {edit.isPending ? <Loader2 className="animate-spin" aria-hidden /> : null}
                Lưu
              </Button>
              <Button size="sm" variant="ghost" type="button" onClick={() => setEditing(false)}>
                Hủy
              </Button>
            </div>
          </form>
        ) : (
          <>
            <h3 className="text-lg font-semibold tracking-tight text-pretty break-words">
              {data.title}
            </h3>
            <QaByline author={data.author} createdAt={data.created_at} />
            <QaThreadBadges thread={data} />
            <Markdown className="text-sm">{data.body}</Markdown>
          </>
        )}
      </header>

      {!editing ? (
        <div className="flex flex-wrap items-center gap-2">
          <Button
            size="sm"
            variant={data.voted ? "default" : "outline"}
            aria-pressed={data.voted}
            disabled={isAuthor || vote.isPending}
            title={
              isAuthor
                ? "Bạn không thể bình chọn câu hỏi của chính mình"
                : "Tôi cũng có câu hỏi này"
            }
            onClick={() => vote.mutate(!data.voted)}
          >
            <ArrowBigUp aria-hidden />
            {data.vote_count}
            <span className="sr-only">lượt bình chọn — tôi cũng có câu hỏi này</span>
          </Button>

          {canModerate ? (
            <Button
              size="sm"
              variant="outline"
              disabled={resolve.isPending}
              onClick={() => resolve.mutate(data.resolved_at === null)}
            >
              {data.resolved_at === null ? (
                <>
                  <CheckCircle2 aria-hidden />
                  Đánh dấu đã giải quyết
                </>
              ) : (
                <>
                  <RotateCcw aria-hidden />
                  Mở lại câu hỏi
                </>
              )}
            </Button>
          ) : null}

          {isAuthor ? (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setEditTitle(data.title);
                setEditBody(data.body);
                setEditing(true);
              }}
            >
              <Pencil aria-hidden />
              Sửa
            </Button>
          ) : null}

          {canModerate ? (
            confirmingDelete ? (
              <span className="flex flex-wrap items-center gap-2">
                <span className="text-sm">Xóa câu hỏi và mọi câu trả lời?</span>
                <Button
                  size="sm"
                  variant="destructive"
                  disabled={removeThread.isPending}
                  onClick={() => removeThread.mutate()}
                >
                  {removeThread.isPending ? (
                    <Loader2 className="animate-spin" aria-hidden />
                  ) : null}
                  Xóa hẳn
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setConfirmingDelete(false)}>
                  Hủy
                </Button>
              </span>
            ) : (
              <Button size="sm" variant="ghost" onClick={() => setConfirmingDelete(true)}>
                <Trash2 aria-hidden />
                Xóa
              </Button>
            )
          ) : null}

          {/* Staff remove things themselves; a report is for everyone else. */}
          {!staff ? (
            <ReportButton
              targetType="qa_thread"
              targetId={data.id}
              authorId={data.author.id}
              className="ml-auto"
            />
          ) : null}
        </div>
      ) : null}

      {failed ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(failed.error, QA_MESSAGES)}</AlertDescription>
        </Alert>
      ) : null}

      <section className="space-y-3 border-t pt-4" aria-label="Câu trả lời">
        <h4 className="text-sm font-semibold">
          {replyTotal === 0 ? "Chưa có câu trả lời" : `${replyTotal} câu trả lời`}
        </h4>

        {replies.isError ? (
          <Alert variant="destructive">
            <AlertDescription>{apiErrorMessage(replies.error, QA_MESSAGES)}</AlertDescription>
          </Alert>
        ) : null}

        <ul className="space-y-3">
          {allReplies.map((reply) => (
            <li
              key={reply.id}
              className={cn(
                "space-y-2 rounded-md border p-3",
                // The answer the reader is most likely looking for stands out
                // from the discussion around it.
                reply.is_instructor_reply && "border-primary/40 bg-primary/5",
              )}
            >
              <div className="flex items-start justify-between gap-2">
                <QaByline
                  author={reply.author}
                  createdAt={reply.created_at}
                  instructor={reply.is_instructor_reply}
                />
                <div className="flex shrink-0 items-center gap-1">
                  {!staff ? (
                    <ReportButton
                      targetType="qa_reply"
                      targetId={reply.id}
                      authorId={reply.author.id}
                    />
                  ) : null}
                  {reply.author.id === currentUserId || staff ? (
                    <Button
                      size="icon"
                      variant="ghost"
                      className="size-7 shrink-0"
                      aria-label="Xóa câu trả lời"
                      disabled={removeReply.isPending}
                      onClick={() => removeReply.mutate(reply)}
                    >
                      <Trash2 aria-hidden />
                    </Button>
                  ) : null}
                </div>
              </div>
              <Markdown className="text-sm">{reply.body}</Markdown>
            </li>
          ))}
        </ul>

        {replies.hasNextPage ? (
          <Button
            size="sm"
            variant="outline"
            onClick={() => replies.fetchNextPage()}
            disabled={replies.isFetchingNextPage}
          >
            {replies.isFetchingNextPage ? <Loader2 className="animate-spin" aria-hidden /> : null}
            Xem thêm câu trả lời
          </Button>
        ) : null}

        <form onSubmit={submitReply} className="space-y-2">
          <Textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder={staff ? "Trả lời học viên…" : "Viết câu trả lời…"}
            rows={3}
            maxLength={QA_BODY_MAX_LENGTH}
            aria-label="Câu trả lời của bạn"
          />
          {answer.isError ? (
            <Alert variant="destructive">
              <AlertDescription>{apiErrorMessage(answer.error, QA_MESSAGES)}</AlertDescription>
            </Alert>
          ) : null}
          <Button type="submit" size="sm" disabled={answer.isPending || draft.trim() === ""}>
            {answer.isPending ? (
              <>
                <Loader2 className="animate-spin" aria-hidden />
                Đang gửi…
              </>
            ) : (
              "Gửi câu trả lời"
            )}
          </Button>
          <p className="text-xs text-muted-foreground">
            Hỗ trợ Markdown — bọc đoạn mã trong ``` để giữ nguyên định dạng.
          </p>
        </form>
      </section>
    </article>
  );
}
