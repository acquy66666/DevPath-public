"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, Plus } from "lucide-react";
import { useId, useState, type FormEvent } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { createLesson, type BuildableLessonType } from "@/lib/api/curriculum";
import { useAuth } from "@/lib/auth/auth-provider";
import { validateLessonTitle } from "@/lib/courses/validation";
import { cn } from "@/lib/utils";

/**
 * Every lesson type the backend knows, now that each one has an editor.
 *
 * `quiz` was held back through phases 2 and 3 for the reason that decides
 * membership of this list: a row no editor can open is worse than an option
 * that is not offered. It joined in phase 4 with `QuizEditor` behind it.
 */
const TYPES: Array<{ value: BuildableLessonType; label: string }> = [
  { value: "video", label: "Video" },
  { value: "article", label: "Bài đọc" },
  { value: "code_exercise", label: "Bài tập code" },
  { value: "quiz", label: "Trắc nghiệm" },
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
      <Button variant="ghost" size="sm" className="text-link" onClick={() => setOpen(true)}>
        <Plus aria-hidden />
        Thêm bài học
      </Button>
    );
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-3 rounded-md border border-border-strong p-3"
      noValidate
    >
      {create.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(create.error)}</AlertDescription>
        </Alert>
      ) : null}

      {/* Four buttons rather than a dropdown: the type decides what the
          lesson will be, and seeing all four at once is the choice. */}
      <fieldset className="flex flex-wrap items-center gap-1.5" disabled={create.isPending}>
        <legend className="float-left mr-1.5 text-body-sm font-medium text-muted-foreground">
          Loại bài
        </legend>
        {TYPES.map((option) => (
          <label
            key={option.value}
            className={cn(
              "relative inline-flex h-8 cursor-pointer items-center rounded-full border px-3 text-[0.8125rem] transition-colors duration-fast has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-ring",
              type === option.value
                ? "border-primary bg-secondary font-semibold text-secondary-foreground"
                : "border-border-strong text-muted-foreground hover:bg-accent hover:text-foreground",
            )}
          >
            <input
              type="radio"
              name={`${typeId}-type`}
              value={option.value}
              checked={type === option.value}
              onChange={() => setType(option.value)}
              className="sr-only"
            />
            {option.label}
          </label>
        ))}
      </fieldset>

      <div className="flex flex-wrap items-start gap-2">
        <div className="min-w-0 flex-1 basis-48">
          <Input
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="Tên bài học"
            aria-label="Tên bài học mới"
            aria-invalid={Boolean(error)}
            disabled={create.isPending}
            autoFocus
          />
          {error ? <p className="mt-1 text-sm text-destructive-text">{error}</p> : null}
        </div>

        <Button type="submit" disabled={create.isPending}>
          {create.isPending ? (
            <>
              <Loader2 className="animate-spin" aria-hidden />
              Đang thêm…
            </>
          ) : (
            "Thêm bài"
          )}
        </Button>
        <Button
          type="button"
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
