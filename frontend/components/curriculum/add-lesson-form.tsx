"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, Plus } from "lucide-react";
import { useId, useState, type FormEvent } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { createLesson, type BuildableLessonType } from "@/lib/api/curriculum";
import { useAuth } from "@/lib/auth/auth-provider";
import { validateLessonTitle } from "@/lib/courses/validation";

/**
 * Only video and article can be added here.
 *
 * Quiz and code exercise are lesson types too, but each arrives with a whole
 * editor of its own in phase 3–4; offering them now would create rows nothing
 * can fill in.
 */
const TYPES: Array<{ value: BuildableLessonType; label: string }> = [
  { value: "video", label: "Video" },
  { value: "article", label: "Bài đọc" },
];

export function AddLessonForm({
  sectionId,
  courseId,
}: {
  sectionId: string;
  courseId: string;
}) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const typeId = useId();

  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [type, setType] = useState<BuildableLessonType>("video");
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () =>
      createLesson(accessToken as string, sectionId, { title: title.trim(), type }),
    onSuccess: () => {
      setTitle("");
      queryClient.invalidateQueries({ queryKey: ["curriculum", courseId] });
    },
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const validation = validateLessonTitle(title);
    setError(validation);
    if (validation) return;
    create.mutate();
  }

  if (!open) {
    return (
      <Button variant="ghost" size="sm" onClick={() => setOpen(true)}>
        <Plus aria-hidden />
        Thêm bài học
      </Button>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-2 rounded-lg border p-2" noValidate>
      {create.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(create.error)}</AlertDescription>
        </Alert>
      ) : null}

      <div className="flex flex-wrap items-start gap-2">
        <div className="min-w-48 flex-1">
          <Input
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="Tên bài học"
            aria-label="Tên bài học mới"
            aria-invalid={Boolean(error)}
            disabled={create.isPending}
            autoFocus
          />
          {error ? <p className="mt-1 text-sm text-destructive">{error}</p> : null}
        </div>

        <NativeSelect
          id={typeId}
          value={type}
          onChange={(event) => setType(event.target.value as BuildableLessonType)}
          aria-label="Loại bài học"
          disabled={create.isPending}
          className="w-32"
        >
          {TYPES.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </NativeSelect>

        <Button type="submit" size="sm" disabled={create.isPending}>
          {create.isPending ? (
            <>
              <Loader2 className="animate-spin" aria-hidden />
              Đang thêm…
            </>
          ) : (
            "Thêm"
          )}
        </Button>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          onClick={() => {
            setOpen(false);
            setTitle("");
            setError(null);
          }}
          disabled={create.isPending}
        >
          Đóng
        </Button>
      </div>
    </form>
  );
}
