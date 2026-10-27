"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Loader2 } from "lucide-react";
import { useId, useState } from "react";

import { ArticleEditor } from "@/components/curriculum/article-editor";
import { ExerciseEditor } from "@/components/exercise/exercise-editor";
import { TranscriptUpload } from "@/components/curriculum/transcript-upload";
import { VideoUpload } from "@/components/curriculum/video-upload";
import { QuizEditor } from "@/components/quiz/quiz-editor";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { getLesson, updateLesson, type Lesson } from "@/lib/api/curriculum";
import { useAuth } from "@/lib/auth/auth-provider";
import { validateLessonTitle } from "@/lib/courses/validation";

/**
 * The editing panel under a lesson row.
 *
 * The row comes from the curriculum tree, which deliberately carries no
 * content -- so opening the panel is what fetches the lesson itself.
 */
export function LessonEditor({
  lessonId,
  courseId,
  onClose,
}: {
  lessonId: string;
  courseId: string;
  onClose: () => void;
}) {
  const { accessToken } = useAuth();

  const query = useQuery({
    queryKey: ["lesson", lessonId],
    queryFn: () => getLesson(lessonId, accessToken),
    enabled: accessToken !== null,
  });

  if (query.isPending) {
    return (
      <div className="border-t p-4 sm:p-5">
        <Skeleton className="h-40" />
      </div>
    );
  }

  if (query.isError) {
    return (
      <div className="border-t p-4 sm:p-5">
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(query.error)}</AlertDescription>
        </Alert>
      </div>
    );
  }

  // Keyed by id so the fields are seeded once, by mounting, rather than by an
  // effect that would fight with whatever is half-typed on every refetch.
  return (
    <LessonForm
      key={query.data.id}
      lesson={query.data}
      courseId={courseId}
      onClose={onClose}
    />
  );
}

function LessonForm({
  lesson,
  courseId,
  onClose,
}: {
  lesson: Lesson;
  courseId: string;
  onClose: () => void;
}) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const titleId = useId();
  const contentId = useId();
  const previewId = useId();

  const [title, setTitle] = useState(lesson.title);
  const [isPreview, setIsPreview] = useState(lesson.is_preview);
  const [content, setContent] = useState(lesson.article_content ?? "");
  const [titleError, setTitleError] = useState<string | null>(null);
  const [uploadingImages, setUploadingImages] = useState(false);

  const save = useMutation({
    mutationFn: () =>
      updateLesson(accessToken as string, lesson.id, {
        title: title.trim(),
        is_preview: isPreview,
        // Left out entirely for a video lesson: a PATCH says what changed, and
        // a video has no article to change.
        ...(lesson.type === "article" ? { article_content: content } : {}),
      }),
    onSuccess: (updated) => {
      queryClient.setQueryData(["lesson", lesson.id], updated);
      // The row above shows the title and the "học thử" badge.
      queryClient.invalidateQueries({ queryKey: ["curriculum", courseId] });
    },
  });

  return (
    <div className="space-y-5 border-t p-4 sm:p-5">
      {save.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(save.error)}</AlertDescription>
        </Alert>
      ) : null}

      <div className="space-y-2">
        <Label htmlFor={titleId}>Tên bài học</Label>
        <Input
          id={titleId}
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          aria-invalid={Boolean(titleError)}
          disabled={save.isPending}
        />
        {titleError ? <p className="text-sm text-destructive-text">{titleError}</p> : null}
      </div>

      {lesson.type === "article" ? (
        <div className="space-y-2">
          <Label htmlFor={contentId}>Nội dung bài đọc</Label>
          <ArticleEditor
            id={contentId}
            lessonId={lesson.id}
            value={content}
            onChange={setContent}
            disabled={save.isPending}
            onUploadingChange={setUploadingImages}
          />
        </div>
      ) : lesson.type === "code_exercise" ? (
        // The exercise is four tables away from the lesson, so it edits itself
        // and saves on its own button rather than riding along with the title.
        <ExerciseEditor lessonId={lesson.id} />
      ) : lesson.type === "quiz" ? (
        // Same arrangement, same reason: the quiz, its questions and their
        // answers are their own tables behind their own endpoints.
        <QuizEditor lessonId={lesson.id} courseId={courseId} />
      ) : (
        <div className="space-y-3">
          <VideoUpload lesson={lesson} />
          <TranscriptUpload lesson={lesson} />
        </div>
      )}

      <div className="flex flex-col gap-4 border-t pt-4 sm:flex-row sm:items-center">
      <div className="flex flex-1 items-start gap-2">
        <input
          id={previewId}
          type="checkbox"
          checked={isPreview}
          onChange={(event) => setIsPreview(event.target.checked)}
          disabled={save.isPending}
          className="mt-1 size-4 rounded border-input accent-primary"
        />
        <div>
          <Label htmlFor={previewId}>Cho học thử</Label>
          <p className="text-sm text-muted-foreground">
            Ai cũng xem được bài này mà không cần đăng ký khóa học — dùng cho 1–2 bài
            mở đầu.
          </p>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <p role="status" className="flex items-center gap-1.5 text-body-sm text-success-text">
          {save.isSuccess && !save.isPending ? (
            <>
              <Check className="size-4" aria-hidden />
              Đã lưu bài học.
            </>
          ) : null}
        </p>
        <Button size="sm" variant="ghost" onClick={onClose} disabled={save.isPending}>
          Đóng
        </Button>
        <Button
          size="sm"
          onClick={() => {
            const error = validateLessonTitle(title);
            setTitleError(error);
            if (error) return;
            save.mutate();
          }}
          // Saving while a picture uploads would save its placeholder.
          disabled={save.isPending || uploadingImages}
        >
          {save.isPending ? (
            <>
              <Loader2 className="animate-spin" aria-hidden />
              Đang lưu…
            </>
          ) : uploadingImages ? (
            "Đang tải ảnh…"
          ) : (
            "Lưu bài học"
          )}
        </Button>
      </div>
      </div>
    </div>
  );
}
