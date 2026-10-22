"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Sparkles } from "lucide-react";
import { useId, useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { getCurriculum, type LessonSummary } from "@/lib/api/curriculum";
import { apiErrorMessage } from "@/lib/api/error-messages";
import {
  GENERATE_DEFAULT,
  GENERATE_MAX,
  GENERATE_MIN,
  generateQuestions,
  type GenerationResult,
} from "@/lib/api/quiz-authoring";
import { useAuth } from "@/lib/auth/auth-provider";

/** Lessons with words in them: an article's text, or a video's transcript. */
const READABLE: ReadonlySet<LessonSummary["type"]> = new Set(["article", "video"]);

/**
 * Draft questions from a lesson of the same course with Gemini.
 *
 * The drafts land in the question list below as "chờ duyệt", and the quiz
 * cannot be published until every one is approved, edited or deleted. There
 * is deliberately no "approve all": a reviewer who approves ten questions in
 * one click has reviewed none of them, and both models tried were measured
 * writing a wrong answer key that looked right.
 *
 * The lesson offered first is the nearest readable one *before* this quiz --
 * the lesson a quiz at the end of it most likely tests.
 */
export function QuizGenerator({
  quizId,
  courseId,
  quizLessonId,
}: {
  quizId: string;
  courseId: string;
  quizLessonId: string;
}) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const fieldId = useId();

  const curriculum = useQuery({
    queryKey: ["curriculum", courseId],
    queryFn: () => getCurriculum(courseId, accessToken),
    enabled: accessToken !== null,
  });

  const sections = (curriculum.data?.sections ?? [])
    .map((section) => ({
      ...section,
      lessons: section.lessons.filter((lesson) => READABLE.has(lesson.type)),
    }))
    .filter((section) => section.lessons.length > 0);

  const ordered = (curriculum.data?.sections ?? []).flatMap((section) => section.lessons);
  const quizAt = ordered.findIndex((lesson) => lesson.id === quizLessonId);
  const suggested =
    ordered
      .slice(0, quizAt === -1 ? ordered.length : quizAt)
      .reverse()
      .find((lesson) => READABLE.has(lesson.type)) ??
    sections[0]?.lessons[0] ??
    null;

  // Null until the instructor picks: the suggestion follows the curriculum as
  // it loads instead of freezing whatever the first render happened to see.
  const [picked, setPicked] = useState<string | null>(null);
  const source = picked ?? suggested?.id ?? "";
  const [count, setCount] = useState(String(GENERATE_DEFAULT));
  const [result, setResult] = useState<GenerationResult | null>(null);

  const generate = useMutation({
    mutationFn: () =>
      generateQuestions(accessToken as string, quizId, source, Number(count)),
    onMutate: () => setResult(null),
    onSuccess: (data) => {
      setResult(data);
      queryClient.invalidateQueries({ queryKey: ["quiz-questions", quizId] });
      queryClient.invalidateQueries({ queryKey: ["quiz"] });
    },
  });

  const countValue = Number(count);
  const countValid =
    Number.isInteger(countValue) && countValue >= GENERATE_MIN && countValue <= GENERATE_MAX;

  if (curriculum.isSuccess && sections.length === 0) {
    return (
      <p className="rounded-md border border-dashed p-3 text-sm text-muted-foreground">
        Khóa học chưa có bài viết hay video nào để AI soạn câu hỏi từ đó.
      </p>
    );
  }

  return (
    <section className="space-y-3 rounded-md border bg-muted/20 p-3">
      <div className="flex items-start gap-2">
        <Sparkles className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
        <div>
          <p className="text-sm font-medium">Sinh câu hỏi bằng AI</p>
          <p className="text-xs text-muted-foreground">
            AI đọc một bài học của khóa và soạn nháp. Bạn duyệt từng câu trước khi xuất bản.
          </p>
        </div>
      </div>

      <form
        className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_6rem_auto] sm:items-end"
        onSubmit={(event) => {
          event.preventDefault();
          if (source && countValid) generate.mutate();
        }}
      >
        <div className="space-y-1.5">
          <Label htmlFor={`${fieldId}-source`}>Soạn từ bài học</Label>
          <NativeSelect
            id={`${fieldId}-source`}
            value={source}
            onChange={(event) => setPicked(event.target.value)}
            disabled={curriculum.isPending || generate.isPending}
          >
            {sections.map((section) => (
              <optgroup key={section.id} label={section.title}>
                {section.lessons.map((lesson) => (
                  <option key={lesson.id} value={lesson.id}>
                    {lesson.title}
                    {lesson.type === "video" ? " (video — đọc transcript)" : ""}
                  </option>
                ))}
              </optgroup>
            ))}
          </NativeSelect>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor={`${fieldId}-count`}>Số câu</Label>
          <Input
            id={`${fieldId}-count`}
            type="number"
            min={GENERATE_MIN}
            max={GENERATE_MAX}
            value={count}
            onChange={(event) => setCount(event.target.value)}
            disabled={generate.isPending}
            aria-invalid={!countValid}
          />
        </div>

        <Button type="submit" disabled={!source || !countValid || generate.isPending}>
          {generate.isPending ? (
            <>
              <Loader2 className="animate-spin" aria-hidden />
              Đang soạn…
            </>
          ) : (
            <>
              <Sparkles aria-hidden />
              Sinh câu hỏi
            </>
          )}
        </Button>
      </form>

      <p className="sr-only" aria-live="polite">
        {generate.isPending
          ? "AI đang soạn câu hỏi."
          : result
            ? `Đã thêm ${result.created} câu hỏi chờ duyệt.`
            : ""}
      </p>

      {generate.isPending ? (
        <p className="text-xs text-muted-foreground">
          AI đang đọc bài và soạn câu hỏi, thường mất vài giây.
        </p>
      ) : null}

      {!countValid ? (
        <p className="text-xs text-destructive">
          Số câu từ {GENERATE_MIN} đến {GENERATE_MAX}.
        </p>
      ) : null}

      {generate.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(generate.error)}</AlertDescription>
        </Alert>
      ) : null}

      {result ? (
        <Alert>
          <AlertDescription className="space-y-1">
            <p>
              Đã thêm {result.created} câu hỏi do AI soạn vào cuối danh sách. Đọc kỹ đáp án và
              lời giải thích của từng câu, rồi bấm <strong>Duyệt</strong>, sửa hoặc xóa.
            </p>
            {result.dropped > 0 ? (
              <p className="text-muted-foreground">
                {result.dropped} câu AI soạn bị loại vì không hợp lệ (không có đáp án đúng,
                phương án trùng nhau, hoặc trùng câu đã có).
              </p>
            ) : null}
            {result.truncated ? (
              <p className="text-muted-foreground">
                Bài học dài nên AI chỉ đọc phần đầu của bài.
              </p>
            ) : null}
          </AlertDescription>
        </Alert>
      ) : null}
    </section>
  );
}
