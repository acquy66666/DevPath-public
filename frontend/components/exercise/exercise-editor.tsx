"use client";

import { useQuery } from "@tanstack/react-query";
import { Code2 } from "lucide-react";

import { ExerciseForm } from "@/components/exercise/exercise-form";
import { TestCaseManager } from "@/components/exercise/test-case-manager";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { ApiError } from "@/lib/api/client";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { getExerciseOfLesson } from "@/lib/api/grading";
import { useAuth } from "@/lib/auth/auth-provider";

/** A lesson with no exercise yet answers 404, which is an answer, not a fault. */
function isMissing(error: unknown): boolean {
  return error instanceof ApiError && error.code === "EXERCISE_NOT_FOUND";
}

/**
 * The authoring panel for a `code_exercise` lesson.
 *
 * The exercise lives in its own tables, so opening the lesson editor is what
 * fetches it -- and a lesson that has none is the normal state of a row that
 * was just created. That case gets the same form with nothing filled in, so
 * creating and editing are one screen rather than a wizard.
 */
export function ExerciseEditor({ lessonId }: { lessonId: string }) {
  const { accessToken } = useAuth();

  const query = useQuery({
    queryKey: ["code-exercise", lessonId],
    queryFn: () => getExerciseOfLesson(lessonId, accessToken),
    enabled: accessToken !== null,
    // A 404 here is the expected answer for a new lesson; retrying it three
    // times would make the common path the slow one.
    retry: (failureCount, error) => !isMissing(error) && failureCount < 2,
  });

  if (query.isPending) {
    return <div className="h-40 animate-pulse rounded-md bg-muted/40" />;
  }

  if (query.isError) {
    if (!isMissing(query.error)) {
      return (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(query.error)}</AlertDescription>
        </Alert>
      );
    }

    return (
      <div className="space-y-4">
        <div className="flex items-start gap-3 rounded-md border border-dashed p-3">
          <div className="flex size-9 shrink-0 items-center justify-center rounded-md bg-muted">
            <Code2 className="size-4 text-muted-foreground" aria-hidden />
          </div>
          <div>
            <p className="font-medium">Bài học này chưa có bài tập</p>
            <p className="text-sm text-muted-foreground">
              Viết đề bài rồi bấm “Tạo bài tập”. Sau đó bạn thêm test case — bài
              tập chưa có test case thì hệ thống không nhận bài nộp.
            </p>
          </div>
        </div>

        <ExerciseForm lessonId={lessonId} exercise={null} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Keyed by id so a freshly created exercise seeds the fields by
          mounting, the same way the lesson editor does. */}
      <ExerciseForm key={query.data.id} lessonId={lessonId} exercise={query.data} />
      <TestCaseManager exerciseId={query.data.id} />
    </div>
  );
}
