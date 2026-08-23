"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Pencil, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
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
 */
export function NotesPanel({
  lessonId,
  timed,
  currentTime,
  onSeek,
}: {
  lessonId: string;
  /** Whether this lesson has a timeline worth stamping notes against. */
  timed: boolean;
  /** Where the player is now, asked for only at the moment a note is written. */
  currentTime: () => number;
  onSeek: (seconds: number) => void;
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

  return (
    <section className="space-y-4">
      <h2 className="text-lg font-semibold tracking-tight">Ghi chú của tôi</h2>

      <form onSubmit={submit} className="space-y-2">
        <Textarea
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder={
            timed
              ? "Ghi lại điều đáng nhớ ở đoạn này…"
              : "Ghi lại điều đáng nhớ trong bài này…"
          }
          rows={3}
          maxLength={2000}
        />

        {add.isError ? (
          <Alert variant="destructive">
            <AlertDescription>{apiErrorMessage(add.error)}</AlertDescription>
          </Alert>
        ) : null}

        <Button type="submit" size="sm" disabled={add.isPending || draft.trim() === ""}>
          {add.isPending ? (
            <>
              <Loader2 className="animate-spin" aria-hidden />
              Đang lưu…
            </>
          ) : (
            "Thêm ghi chú"
          )}
        </Button>
      </form>

      {notes.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(notes.error)}</AlertDescription>
        </Alert>
      ) : null}

      {notes.data && notes.data.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          Chưa có ghi chú nào cho bài học này.
        </p>
      ) : null}

      <ul className="space-y-3">
        {notes.data?.map((note) => (
          <li key={note.id} className="rounded-lg border p-3">
            <div className="flex items-start justify-between gap-3">
              {timed ? (
                <button
                  type="button"
                  onClick={() => onSeek(note.timestamp_s)}
                  className="shrink-0 rounded bg-muted px-2 py-0.5 font-mono text-xs hover:bg-muted/70"
                  aria-label={`Tua tới ${formatTimestamp(note.timestamp_s)}`}
                >
                  {formatTimestamp(note.timestamp_s)}
                </button>
              ) : null}

              <div className="flex shrink-0 gap-1">
                <Button
                  size="icon"
                  variant="ghost"
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
                  aria-label="Xóa ghi chú"
                  onClick={() => remove.mutate(note)}
                  disabled={remove.isPending}
                >
                  <Trash2 aria-hidden />
                </Button>
              </div>
            </div>

            {editing === note.id ? (
              <div className="mt-2 space-y-2">
                <Textarea
                  value={editDraft}
                  onChange={(event) => setEditDraft(event.target.value)}
                  rows={3}
                  maxLength={2000}
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
              <p className="mt-1 whitespace-pre-line text-sm">{note.content}</p>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
