"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Clock, Loader2, Pencil, Play, Plus, Trash2 } from "lucide-react";
import { useState, type FormEvent, type Ref } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { apiErrorMessage } from "@/lib/api/error-messages";
import {
  createNote,
  deleteNote,
  listNotes,
  updateNote,
  type Note,
} from "@/lib/api/study";
import { useAuth } from "@/lib/auth/auth-provider";
import { formatTimestamp } from "@/lib/format";

/**
 * The notes a reader keeps on one lesson.
 *
 * A note carries the second it was written at, so the list doubles as a set of
 * bookmarks inside the video: clicking the timestamp jumps there. On a lesson
 * with no timeline -- an article -- the timestamp is zero and simply is not
 * shown.
 *
 * The box is one card with its button in a footer, the list another card with
 * a row per note: the two read as "write" and "what you wrote", and the
 * buttons of a row stay out of the way of its text.
 */
export function NotesPanel({
  lessonId,
  timed,
  currentTime,
  onSeek,
  composerRef,
}: {
  lessonId: string;
  /** Whether this lesson has a timeline worth stamping notes against. */
  timed: boolean;
  /** Where the player is now, asked for only at the moment a note is written. */
  currentTime: () => number;
  onSeek: (seconds: number) => void;
  /** The note box, for "Ghi chú tại …" under the player to put the cursor in. */
  composerRef?: Ref<HTMLTextAreaElement>;
}) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState("");

  const notes = useQuery({
    queryKey: ["notes", lessonId],
    queryFn: () => listNotes(accessToken as string, lessonId),
    enabled: accessToken !== null,
  });

  const refresh = () =>
    queryClient.invalidateQueries({ queryKey: ["notes", lessonId] });

  const add = useMutation({
    mutationFn: () =>
      createNote(accessToken as string, lessonId, {
        content: draft.trim(),
        // Read at submit time, not at render time: the video has moved on
        // since this panel drew itself.
        timestamp_s: timed ? currentTime() : 0,
      }),
    onSuccess: () => {
      setDraft("");
      refresh();
    },
  });

  const edit = useMutation({
    mutationFn: (note: Note) =>
      updateNote(accessToken as string, note.id, { content: editDraft.trim() }),
    onSuccess: () => {
      setEditing(null);
      refresh();
    },
  });

  const remove = useMutation({
    mutationFn: (note: Note) => deleteNote(accessToken as string, note.id),
    onSuccess: refresh,
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (draft.trim().length === 0) return;
    add.mutate();
  }

  const count = notes.data?.length ?? 0;

  return (
    <section aria-label="Ghi chú của tôi" className="flex flex-col gap-5">
      <form
        onSubmit={submit}
        className="overflow-hidden rounded-lg border bg-card outline-offset-2 outline-ring has-[textarea:focus-visible]:outline-2"
      >
        <label htmlFor={`ghi-chu-${lessonId}`} className="sr-only">
          Ghi chú mới
        </label>
        <Textarea
          id={`ghi-chu-${lessonId}`}
          ref={composerRef}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder={
            timed
              ? "Ghi lại điều đáng nhớ ở đoạn này…"
              : "Ghi lại điều đáng nhớ trong bài này…"
          }
          rows={3}
          maxLength={2000}
          // The card is the field's frame; its own border and ring would
          // draw a box inside a box. Focus still shows: the card takes it.
          className="min-h-22 rounded-none border-0 bg-transparent px-4 py-3.5 shadow-none focus-visible:outline-none"
        />
        <div className="flex flex-col items-stretch gap-2 border-t border-muted bg-background px-3 py-2.5 sm:flex-row sm:items-center sm:justify-between sm:pl-4">
          <p className="flex items-center gap-1.5 text-caption text-muted-foreground">
            {timed ? (
              <>
                <Clock className="size-3.5 shrink-0" aria-hidden />
                Ghi chú giữ mốc thời gian của video lúc bạn lưu
              </>
            ) : (
              "Chỉ mình bạn đọc được ghi chú này"
            )}
          </p>
          <Button
            type="submit"
            variant="secondary"
            className="h-11 sm:h-9"
            disabled={add.isPending || draft.trim() === ""}
          >
            {add.isPending ? (
              <>
                <Loader2 className="animate-spin" aria-hidden />
                Đang lưu…
              </>
            ) : (
              <>
                <Plus aria-hidden />
                Thêm ghi chú
              </>
            )}
          </Button>
        </div>
      </form>

      {add.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(add.error)}</AlertDescription>
        </Alert>
      ) : null}

      {notes.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(notes.error)}</AlertDescription>
        </Alert>
      ) : null}

      {notes.isPending ? <Skeleton className="h-28 rounded-lg" /> : null}

      {notes.data && count === 0 ? (
        <EmptyState
          mood="empty-notes"
          size="md"
          title="Chưa có ghi chú nào cho bài học này"
          description={
            timed
              ? "Gõ vào ô bên trên khi xem video: ghi chú giữ luôn mốc thời gian, bấm vào là tua tới đó."
              : "Gõ vào ô bên trên để ghi lại ý chính, chỉ mình bạn đọc được."
          }
        />
      ) : null}

      {count > 0 ? (
        <div className="flex flex-col gap-2.5">
          <h2 className="text-body-sm font-semibold text-muted-foreground">
            {count} ghi chú{timed ? " · theo thứ tự trong video" : null}
          </h2>
          <ul className="overflow-hidden rounded-lg border bg-card">
            {notes.data?.map((note) => (
              <li
                key={note.id}
                className="flex flex-col gap-1.5 border-t border-muted py-3 pr-2 pl-3.5 first:border-t-0 sm:flex-row sm:items-start sm:gap-3.5 sm:py-3.5 sm:pr-3 sm:pl-4"
              >
                <div className="flex items-center justify-between sm:contents">
                  {timed ? (
                    <button
                      type="button"
                      onClick={() => onSeek(note.timestamp_s)}
                      className="inline-flex h-7 shrink-0 items-center gap-1.5 rounded-full bg-secondary px-2.5 font-mono text-code text-secondary-foreground tabular-nums transition-colors duration-fast hover:bg-secondary-hover sm:order-first"
                      aria-label={`Tua tới ${formatTimestamp(note.timestamp_s)}`}
                    >
                      <Play className="size-3 fill-current" aria-hidden />
                      {formatTimestamp(note.timestamp_s)}
                    </button>
                  ) : (
                    <span className="sm:hidden" />
                  )}
                  <div className="flex shrink-0 gap-0.5 sm:order-last">
                    <Button
                      size="icon"
                      variant="ghost"
                      className="size-10 text-muted-foreground sm:size-8"
                      aria-label="Sửa ghi chú"
                      onClick={() => {
                        setEditing(note.id);
                        setEditDraft(note.content);
                      }}
                    >
                      <Pencil aria-hidden />
                    </Button>
                    <Button
                      size="icon"
                      variant="ghost"
                      className="size-10 text-muted-foreground sm:size-8"
                      aria-label="Xóa ghi chú"
                      onClick={() => remove.mutate(note)}
                      disabled={remove.isPending}
                    >
                      <Trash2 aria-hidden />
                    </Button>
                  </div>
                </div>

                {editing === note.id ? (
                  <div className="flex min-w-0 flex-1 flex-col gap-2">
                    <Textarea
                      value={editDraft}
                      onChange={(event) => setEditDraft(event.target.value)}
                      rows={3}
                      maxLength={2000}
                      aria-label="Sửa ghi chú"
                    />
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        onClick={() => edit.mutate(note)}
                        disabled={edit.isPending || editDraft.trim() === ""}
                      >
                        Lưu
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => setEditing(null)}>
                        Hủy
                      </Button>
                    </div>
                  </div>
                ) : (
                  <p className="min-w-0 flex-1 text-body whitespace-pre-line break-words sm:pt-0.5">
                    {note.content}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
