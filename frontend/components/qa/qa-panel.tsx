"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, MessageCircleQuestion, Plus } from "lucide-react";
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

import { QA_KEY, QaPager, QaThreadRow } from "./qa-shared";
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
  accessToken,
  currentUserId,
  openThreadId,
  onOpenThread,
}: {
  lessonId: string;
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

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <label htmlFor="qa-sort" className="text-sm text-muted-foreground">
            Sắp xếp
          </label>
          <NativeSelect
            id="qa-sort"
            className="w-auto"
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
          <Button size="sm" onClick={() => setComposing(true)}>
            <Plus aria-hidden />
            Đặt câu hỏi
          </Button>
        ) : null}
      </div>

      {composing ? (
        <form onSubmit={submit} className="space-y-2 rounded-lg border p-3">
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
              size="sm"
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
            <Button type="button" size="sm" variant="ghost" onClick={() => setComposing(false)}>
              Hủy
            </Button>
            <span className="text-xs text-muted-foreground">
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
        <div className="space-y-3" aria-hidden>
          {[0, 1].map((row) => (
            <div key={row} className="h-24 animate-pulse rounded-lg border bg-muted/40" />
          ))}
        </div>
      ) : null}

      {threads.data && threads.data.total === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed px-4 py-8 text-center">
          <MessageCircleQuestion className="size-8 text-muted-foreground" aria-hidden />
          <p className="font-medium">Chưa có câu hỏi nào cho bài học này</p>
          <p className="text-sm text-muted-foreground">
            Chỗ nào chưa rõ, cứ hỏi — giảng viên và các bạn cùng khóa sẽ trả lời.
          </p>
        </div>
      ) : null}

      {threads.data && threads.data.items.length > 0 ? (
        <ul
          className={threads.isPlaceholderData ? "space-y-3 opacity-60" : "space-y-3"}
          aria-busy={threads.isFetching}
        >
          {threads.data.items.map((thread) => (
            <QaThreadRow key={thread.id} thread={thread} onOpen={() => onOpenThread(thread.id)} />
          ))}
        </ul>
      ) : null}

      {threads.data ? (
        <QaPager
          page={threads.data.page}
          pageSize={threads.data.page_size}
          total={threads.data.total}
          onPage={setPage}
        />
      ) : null}
    </section>
  );
}
