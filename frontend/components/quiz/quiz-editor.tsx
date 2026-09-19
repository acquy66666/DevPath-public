"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Check, CheckCircle2, ListChecks, Pencil, Trash2 } from "lucide-react";
import { useId, useState } from "react";

import { QuestionForm } from "@/components/quiz/question-form";
import { QuizGenerator } from "@/components/quiz/quiz-generator";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api/client";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { getQuizOfLesson } from "@/lib/api/quiz";
import {
  approveQuestion,
  createQuiz,
  deleteQuestion,
  listQuestions,
  updateQuiz,
  type Question,
} from "@/lib/api/quiz-authoring";
import { useAuth } from "@/lib/auth/auth-provider";
import { cn } from "@/lib/utils";

/** A lesson with no quiz yet answers 404, which is an answer, not a fault. */
function isMissing(error: unknown): boolean {
  return error instanceof ApiError && error.code === "QUIZ_NOT_FOUND";
}

/**
 * The authoring panel for a `quiz` lesson.
 *
 * The rule the layout is built around: **a published quiz's questions are
 * frozen.** Somebody may be sitting it right now, and they will be marked
 * against `correct_index` as it stands when they submit — so editing the key
 * underneath them would mark them on a question they were never shown. The
 * backend refuses it; this panel says so up front and offers the one move that
 * makes editing possible again, instead of letting an instructor discover the
 * rule through a failed request.
 */
export function QuizEditor({ lessonId, courseId }: { lessonId: string; courseId: string }) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const fieldId = useId();

  const [editing, setEditing] = useState<Question | null>(null);
  const [adding, setAdding] = useState(false);

  const quiz = useQuery({
    queryKey: ["quiz", lessonId],
    queryFn: () => getQuizOfLesson(lessonId, accessToken as string),
    enabled: accessToken !== null,
    retry: (failureCount, error) => !isMissing(error) && failureCount < 2,
  });
  const quizId = quiz.data?.id ?? null;

  const questions = useQuery({
    queryKey: ["quiz-questions", quizId],
    queryFn: () => listQuestions(accessToken as string, quizId as string),
    enabled: quizId !== null,
  });

  const create = useMutation({
    mutationFn: () => createQuiz(accessToken as string, lessonId, {}),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["quiz", lessonId] }),
  });

  const settings = useMutation({
    mutationFn: (changes: Parameters<typeof updateQuiz>[2]) =>
      updateQuiz(accessToken as string, quizId as string, changes),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["quiz", lessonId] }),
  });

  // One question at a time, on purpose: there is no "approve all". Approving
  // ten drafts in one click is reviewing none of them.
  const approve = useMutation({
    mutationFn: (questionId: string) => approveQuestion(accessToken as string, questionId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["quiz-questions", quizId] }),
  });

  const remove = useMutation({
    mutationFn: (questionId: string) => deleteQuestion(accessToken as string, questionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["quiz-questions", quizId] });
      queryClient.invalidateQueries({ queryKey: ["quiz", lessonId] });
    },
  });

  if (quiz.isPending) {
    return <div className="h-40 animate-pulse rounded-lg bg-muted/40" />;
  }

  if (quiz.isError) {
    if (!isMissing(quiz.error)) {
      return (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(quiz.error)}</AlertDescription>
        </Alert>
      );
    }

    return (
      <div className="space-y-4">
        <div className="flex items-start gap-3 rounded-lg border border-dashed p-3">
          <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-muted">
            <ListChecks className="size-4 text-muted-foreground" aria-hidden />
          </div>
          <div>
            <p className="font-medium">Bài học này chưa có bài trắc nghiệm</p>
            <p className="text-sm text-muted-foreground">
              Tạo bài rồi thêm câu hỏi. Học viên chỉ thấy khi bạn bấm xuất bản.
            </p>
          </div>
        </div>

        {create.isError ? (
          <Alert variant="destructive">
            <AlertDescription>{apiErrorMessage(create.error)}</AlertDescription>
          </Alert>
        ) : null}

        <Button onClick={() => create.mutate()} disabled={create.isPending}>
          Tạo bài trắc nghiệm
        </Button>
      </div>
    );
  }

  const data = quiz.data;
  const frozen = data.is_published;
  const rows = questions.data ?? [];
  const unreviewed = rows.filter((row) => row.ai_generated && row.reviewed_at === null).length;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={frozen ? "default" : "secondary"}>
          {frozen ? "Đang xuất bản" : "Bản nháp"}
        </Badge>
        <Badge variant="secondary">{data.question_count} câu</Badge>
        {data.ai_generated ? <Badge variant="secondary">Sinh bằng AI</Badge> : null}
      </div>

      {frozen ? (
        <Alert>
          <AlertDescription>
            Câu hỏi bị khóa khi bài đang xuất bản — có thể đang có học viên làm dở, và
            sửa đáp án lúc này là chấm họ trên một đề khác. Gỡ xuất bản rồi sửa.
          </AlertDescription>
        </Alert>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor={`${fieldId}-limit`}>Thời gian làm bài (phút)</Label>
          <Input
            id={`${fieldId}-limit`}
            type="number"
            min={1}
            max={120}
            defaultValue={data.time_limit_s === null ? "" : Math.round(data.time_limit_s / 60)}
            placeholder="Bỏ trống: không tính giờ"
            onBlur={(event) => {
              const raw = event.target.value.trim();
              const next = raw === "" ? null : Number(raw) * 60;
              if (next !== data.time_limit_s) settings.mutate({ time_limit_s: next });
            }}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor={`${fieldId}-pass`}>Điểm đạt (%)</Label>
          <Input
            id={`${fieldId}-pass`}
            type="number"
            min={0}
            max={100}
            defaultValue={data.pass_score}
            onBlur={(event) => {
              const next = Number(event.target.value);
              if (Number.isFinite(next) && next !== data.pass_score) {
                settings.mutate({ pass_score: next });
              }
            }}
          />
        </div>
      </div>

      {settings.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(settings.error)}</AlertDescription>
        </Alert>
      ) : null}

      {frozen ? null : (
        <QuizGenerator quizId={data.id} courseId={courseId} quizLessonId={lessonId} />
      )}

      {approve.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(approve.error)}</AlertDescription>
        </Alert>
      ) : null}

      <ol className="space-y-2">
        {rows.map((row, index) => (
          <li key={row.id} className="rounded-lg border p-3">
            {editing?.id === row.id ? (
              <QuestionForm
                quizId={data.id}
                question={row}
                onDone={() => setEditing(null)}
              />
            ) : (
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 space-y-1">
                  {row.ai_generated ? (
                    <Badge
                      variant="outline"
                      className={cn(
                        row.reviewed_at === null &&
                          "border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-200",
                      )}
                    >
                      {row.reviewed_at === null ? "AI soạn · chờ duyệt" : "AI soạn · đã duyệt"}
                    </Badge>
                  ) : null}
                  <p className="font-medium">
                    Câu {index + 1}. {row.question}
                  </p>
                  <ul className="space-y-0.5 text-sm text-muted-foreground">
                    {row.options.map((option, optionIndex) => (
                      <li
                        key={optionIndex}
                        className={cn(
                          "flex items-center gap-1.5",
                          optionIndex === row.correct_index && "text-emerald-700",
                        )}
                      >
                        {optionIndex === row.correct_index ? (
                          <CheckCircle2 className="size-3.5 shrink-0" aria-hidden />
                        ) : (
                          <span className="inline-block size-3.5 shrink-0" />
                        )}
                        {option}
                      </li>
                    ))}
                  </ul>
                  {row.explanation ? (
                    <p className="text-sm text-muted-foreground">
                      <span className="font-medium">Giải thích:</span> {row.explanation}
                    </p>
                  ) : null}
                  {row.key_warning ? (
                    <p className="flex items-start gap-1.5 text-sm text-amber-700 dark:text-amber-300">
                      <AlertTriangle className="mt-0.5 size-3.5 shrink-0" aria-hidden />
                      Lời giải thích có vẻ nói về một phương án khác với đáp án đang chọn.
                      Kiểm tra lại đáp án trước khi duyệt.
                    </p>
                  ) : null}
                </div>
                <div className="flex shrink-0 gap-1">
                  {row.ai_generated && row.reviewed_at === null ? (
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={frozen || approve.isPending}
                      onClick={() => approve.mutate(row.id)}
                      aria-label={`Duyệt câu ${index + 1}`}
                    >
                      <Check className="size-4" aria-hidden />
                      Duyệt
                    </Button>
                  ) : null}
                  <Button
                    variant="ghost"
                    size="icon"
                    disabled={frozen}
                    onClick={() => setEditing(row)}
                    aria-label={`Sửa câu ${index + 1}`}
                  >
                    <Pencil className="size-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    disabled={frozen || remove.isPending}
                    onClick={() => remove.mutate(row.id)}
                    aria-label={`Xóa câu ${index + 1}`}
                  >
                    <Trash2 className="size-4" />
                  </Button>
                </div>
              </div>
            )}
          </li>
        ))}
      </ol>

      {adding ? (
        <QuestionForm quizId={data.id} question={null} onDone={() => setAdding(false)} />
      ) : (
        <Button variant="outline" disabled={frozen} onClick={() => setAdding(true)}>
          Thêm câu hỏi
        </Button>
      )}

      <div className="flex items-center gap-2 border-t pt-3">
        <Button
          variant={frozen ? "outline" : "default"}
          disabled={settings.isPending || (!frozen && (rows.length === 0 || unreviewed > 0))}
          onClick={() => settings.mutate({ is_published: !frozen })}
        >
          {frozen ? "Gỡ xuất bản" : "Xuất bản cho học viên"}
        </Button>
        {!frozen && rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">Thêm ít nhất một câu hỏi đã.</p>
        ) : !frozen && unreviewed > 0 ? (
          <p className="text-sm text-muted-foreground">
            Còn {unreviewed} câu AI soạn chưa duyệt.
          </p>
        ) : null}
      </div>
    </div>
  );
}
