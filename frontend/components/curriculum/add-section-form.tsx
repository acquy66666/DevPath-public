"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, Plus } from "lucide-react";
import { useState, type FormEvent } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { createSection } from "@/lib/api/curriculum";
import { useAuth } from "@/lib/auth/auth-provider";
import { validateSectionTitle } from "@/lib/courses/validation";

export function AddSectionForm({
  courseId,
  sectionCount,
}: {
  courseId: string;
  sectionCount: number;
}) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () => createSection(accessToken as string, courseId, title.trim()),
    onSuccess: () => {
      // Cleared before the refetch lands, so the next chương can be typed
      // straight away -- adding several in a row is the normal case.
      setTitle("");
      queryClient.invalidateQueries({ queryKey: ["curriculum", courseId] });
    },
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const validation = validateSectionTitle(title);
    setError(validation);
    if (validation) return;
    create.mutate();
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-2" noValidate>
      {create.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(create.error)}</AlertDescription>
        </Alert>
      ) : null}

      <div className="flex items-start gap-2">
        <div className="flex-1">
          <Input
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder={
              sectionCount === 0
                ? "Tên chương đầu tiên, ví dụ: Nhập môn"
                : `Tên chương ${sectionCount + 1}`
            }
            aria-label="Tên chương mới"
            aria-invalid={Boolean(error)}
            disabled={create.isPending}
          />
          {error ? <p className="mt-1 text-sm text-destructive">{error}</p> : null}
        </div>
        <Button type="submit" variant="outline" disabled={create.isPending}>
          {create.isPending ? (
            <>
              <Loader2 className="animate-spin" aria-hidden />
              Đang thêm…
            </>
          ) : (
            <>
              <Plus aria-hidden />
              Thêm chương
            </>
          )}
        </Button>
      </div>
    </form>
  );
}
