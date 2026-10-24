"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Plus } from "lucide-react";
import { useState, type FormEvent } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { Textarea } from "@/components/ui/textarea";
import { apiErrorMessage } from "@/lib/api/error-messages";
import {
  createThread,
  listLessonThreads,
  QA_BODY_MAX_LENGTH,
  QA_TITLE_MAX_LENGTH,
  type QaSort,
} from "@/lib/api/qa";

import { Pager } from "@/components/ui/pager";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";

import { cn } from "@/lib/utils";

import { QA_KEY, QaThreadRow } from "./qa-shared";
import { QA_MESSAGES, QaThreadView } from "./qa-thread-view";

/**
 * The questions under one lesson, on the learning page.
 *
 * Which thread is open lives in the URL (`?hoi-dap=`), owned by the page: the
 * back button closes it, and a link -- from a notification, say -- opens
 * straight onto it. Everything else (sort, page, the draft) is this panel's.
 */
export function QaPanel({
  lessonId,
  lessonTitle,
  accessToken,
  currentUserId,
  openThreadId,
  onOpenThread,
}: {
  lessonId: string;
  /** Named on the form, so a question is asked about the right lesson. */
  lessonTitle: string;
  accessToken: string;
  currentUserId: string | null;
  openThreadId: string | null;
  onOpenThread: (threadId: string | null) => void;
}) {
  const queryClient = useQueryClient();
  const [sort, setSort] = useState<QaSort>("newest");
  const [page, setPage] = useState(1);
  const [composing, setComposing] = useState(false);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");

  const threads = useQuery({
    queryKey: [...QA_KEY, "lesson", lessonId, sort, page],
    queryFn: () => listLessonThreads(accessToken, lessonId, { sort, page }),
    enabled: openThreadId === null,
    placeholderData: keepPreviousData,
  });

  const ask = useMutation({
    mutationFn: () => createThread(accessToken, lessonId, { title: title.trim(), body: body.trim() }),
    onSuccess: (thread) => {
      setComposing(false);
      setTitle("");
      setBody("");
      queryClient.invalidateQueries({ queryKey: QA_KEY });
      onOpenThread(thread.id);
    },
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (title.trim() === "" || body.trim() === "") return;
    ask.mutate();
  }

  if (openThreadId !== null) {
    return (
      <QaThreadView
        key={openThreadId}
        threadId={openThreadId}
        accessToken={accessToken}
        currentUserId={currentUserId}
        // The learning page is for enrolled learners; the course's staff read
        // its questions from their inbox, where this is true.
        staff={false}
        onBack={() => onOpenThread(null)}
        backLabel="Tất cả câu hỏi của bài này"
      />
    );
  }

  const total = threads.data?.total ?? null;

  return (
    <section aria-label="Hỏi đáp" className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          {total !== null ? (
            <h2 className="text-body-sm font-semibold text-muted-foreground">{total} câu hỏi</h2>
          ) : null}
          <label htmlFor="qa-sort" className="sr-only">
            Sắp xếp câu hỏi
          </label>
          <NativeSelect
            id="qa-sort"
            className="h-9 w-auto text-body-sm"
            value={sort}
            onChange={(event) => {
              setSort(event.target.value as QaSort);
              setPage(1);
            }}
          >
            <option value="newest">Mới nhất</option>
            <option value="top">Nhiều người hỏi nhất</option>
          </NativeSelect>
        </div>
        {!composing ? (
          <Button variant="secondary" onClick={() => setComposing(true)}>
            <Plus aria-hidden />
            Đặt câu hỏi
          </Button>
        ) : null}
      </div>

      {composing ? (
        <form onSubmit={submit} className="flex flex-col gap-2.5 rounded-lg border bg-card p-4">
          <p className="text-title text-pretty">Câu hỏi mới về bài “{lessonTitle}”</p>
          <Input
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="Tóm tắt câu hỏi trong một dòng"
            maxLength={QA_TITLE_MAX_LENGTH}
            aria-label="Tiêu đề câu hỏi"
            autoFocus
          />
          <Textarea
            value={body}
            onChange={(event) => setBody(event.target.value)}
            placeholder="Bạn đang vướng ở đâu? Dán đoạn mã và thông báo lỗi nếu có."
            rows={5}
            maxLength={QA_BODY_MAX_LENGTH}
            aria-label="Nội dung câu hỏi"
          />
          {ask.isError ? (
            <Alert variant="destructive">
              <AlertDescription>{apiErrorMessage(ask.error, QA_MESSAGES)}</AlertDescription>
            </Alert>
          ) : null}
          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="submit"
              variant="secondary"
              disabled={ask.isPending || title.trim() === "" || body.trim() === ""}
            >
              {ask.isPending ? (
                <>
                  <Loader2 className="animate-spin" aria-hidden />
                  Đang gửi…
                </>
              ) : (
                "Gửi câu hỏi"
              )}
            </Button>
            <Button type="button" variant="ghost" onClick={() => setComposing(false)}>
              Hủy
            </Button>
            <span className="text-caption text-muted-foreground">
              Hỗ trợ Markdown — bọc đoạn mã trong ```.
            </span>
          </div>
        </form>
      ) : null}

      {threads.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(threads.error, QA_MESSAGES)}</AlertDescription>
        </Alert>
      ) : null}

      {threads.isPending ? (
        <div className="flex flex-col gap-2.5" aria-hidden>
          {[0, 1].map((row) => (
            <Skeleton key={row} className="h-28 rounded-lg" />
          ))}
        </div>
      ) : null}

      {threads.data && threads.data.total === 0 && !composing ? (
        <EmptyState
          size="md"
          title="Chưa có câu hỏi nào cho bài học này"
          description="Chỗ nào chưa rõ, bấm “Đặt câu hỏi”: giảng viên và các bạn cùng khóa sẽ trả lời."
        />
      ) : null}

      {threads.data && threads.data.items.length > 0 ? (
        <ul
          className={cn("flex flex-col gap-2.5", threads.isPlaceholderData && "opacity-60")}
          aria-busy={threads.isFetching}
        >
          {threads.data.items.map((thread) => (
            <QaThreadRow key={thread.id} thread={thread} onOpen={() => onOpenThread(thread.id)} />
          ))}
        </ul>
      ) : null}

      {threads.data ? (
        <Pager
          page={threads.data.page}
          pageSize={threads.data.page_size}
          total={threads.data.total}
          onPage={setPage}
        />
      ) : null}
    </section>
  );
}
