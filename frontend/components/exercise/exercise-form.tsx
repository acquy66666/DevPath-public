"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, Loader2 } from "lucide-react";
import { useId, useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { apiErrorMessage } from "@/lib/api/error-messages";
import {
  createExercise,
  updateExercise,
  type CodeExercise,
} from "@/lib/api/grading";
import { useAuth } from "@/lib/auth/auth-provider";
import {
  DEFAULT_MEMORY_LIMIT_MB,
  DEFAULT_TIME_LIMIT_MS,
  MAX_MEMORY_LIMIT_MB,
  MAX_TIME_LIMIT_MS,
  MIN_MEMORY_LIMIT_MB,
  MIN_TIME_LIMIT_MS,
  validateMemoryLimit,
  validateStatement,
  validateTimeLimit,
} from "@/lib/grading/validation";

const STATEMENT_PLACEHOLDER = `Mô tả bài toán bằng Markdown.

**Đầu vào:** dòng đầu là số nguyên n…

**Đầu ra:** một số nguyên duy nhất…

**Ví dụ**

Vào: 5 / Ra: 3`;

interface Errors {
  statement: string | null;
  time: string | null;
  memory: string | null;
}

const NO_ERRORS: Errors = { statement: null, time: null, memory: null };

/**
 * The statement and the limits, for one lesson.
 *
 * One form for both cases: `exercise` is null on a lesson that has no exercise
 * yet, and saving creates it. The two are the same fields, and a separate
 * create form would be the same code with one verb changed.
 */
export function ExerciseForm({
  lessonId,
  exercise,
}: {
  lessonId: string;
  exercise: CodeExercise | null;
}) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const statementId = useId();
  const starterId = useId();
  const timeId = useId();
  const memoryId = useId();

  const [statement, setStatement] = useState(exercise?.statement_md ?? "");
  const [starter, setStarter] = useState(exercise?.starter_code ?? "");
  const [time, setTime] = useState(
    String(exercise?.time_limit_ms ?? DEFAULT_TIME_LIMIT_MS),
  );
  const [memory, setMemory] = useState(
    String(exercise?.memory_limit_mb ?? DEFAULT_MEMORY_LIMIT_MB),
  );
  const [errors, setErrors] = useState<Errors>(NO_ERRORS);

  const save = useMutation({
    mutationFn: () => {
      const payload = {
        statement_md: statement.trim(),
        // Empty means no starter code, not an empty file: the editor on the
        // student's side would otherwise open on a blank line that looks
        // deliberate.
        starter_code: starter.trim() ? starter : null,
        time_limit_ms: Number(time.trim()),
        memory_limit_mb: Number(memory.trim()),
      };

      return exercise === null
        ? createExercise(accessToken as string, lessonId, payload)
        : updateExercise(accessToken as string, exercise.id, payload);
    },
    onSuccess: (saved) => {
      queryClient.setQueryData(["code-exercise", lessonId], saved);
      // On the create path the query is sitting on a 404; refetching is what
      // moves it out of the error branch and reveals the test case list.
      queryClient.invalidateQueries({ queryKey: ["code-exercise", lessonId] });
    },
  });

  function handleSave() {
    const next: Errors = {
      statement: validateStatement(statement),
      time: validateTimeLimit(time),
      memory: validateMemoryLimit(memory),
    };
    setErrors(next);
    if (next.statement || next.time || next.memory) return;
    save.mutate();
  }

  return (
    <div className="space-y-4">
      {save.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(save.error)}</AlertDescription>
        </Alert>
      ) : null}

      <div className="space-y-2">
        <Label htmlFor={statementId}>Đề bài</Label>
        <Textarea
          id={statementId}
          value={statement}
          onChange={(event) => setStatement(event.target.value)}
          rows={10}
          placeholder={STATEMENT_PLACEHOLDER}
          aria-invalid={Boolean(errors.statement)}
          disabled={save.isPending}
        />
        {errors.statement ? (
          <p className="text-sm text-destructive-text">{errors.statement}</p>
        ) : (
          <p className="text-sm text-muted-foreground">
            Markdown được hỗ trợ. Viết rõ định dạng đầu vào và đầu ra — học viên
            chấm đúng hay sai bằng đúng những dòng bạn mô tả ở đây.
          </p>
        )}
      </div>

      <div className="space-y-2">
        <Label htmlFor={starterId}>Code mở đầu</Label>
        <Textarea
          id={starterId}
          value={starter}
          onChange={(event) => setStarter(event.target.value)}
          rows={6}
          className="font-mono text-sm"
          placeholder={"n = int(input())\n\n# Viết code của bạn ở đây"}
          disabled={save.isPending}
        />
        <p className="text-sm text-muted-foreground">
          Nội dung có sẵn trong ô soạn thảo của học viên. Để trống nếu muốn họ
          bắt đầu từ trang giấy trắng.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor={timeId}>Giới hạn thời gian (ms)</Label>
          <Input
            id={timeId}
            value={time}
            onChange={(event) => setTime(event.target.value)}
            inputMode="numeric"
            aria-invalid={Boolean(errors.time)}
            disabled={save.isPending}
          />
          <p
            className={
              errors.time ? "text-sm text-destructive-text" : "text-sm text-muted-foreground"
            }
          >
            {errors.time ?? `Mỗi test case, từ ${MIN_TIME_LIMIT_MS} đến ${MAX_TIME_LIMIT_MS} ms.`}
          </p>
        </div>

        <div className="space-y-2">
          <Label htmlFor={memoryId}>Giới hạn bộ nhớ (MB)</Label>
          <Input
            id={memoryId}
            value={memory}
            onChange={(event) => setMemory(event.target.value)}
            inputMode="numeric"
            aria-invalid={Boolean(errors.memory)}
            disabled={save.isPending}
          />
          <p
            className={
              errors.memory
                ? "text-sm text-destructive-text"
                : "text-sm text-muted-foreground"
            }
          >
            {errors.memory ??
              `Từ ${MIN_MEMORY_LIMIT_MB} đến ${MAX_MEMORY_LIMIT_MB} MB. Vượt quá là verdict MLE.`}
          </p>
        </div>
      </div>

      <p className="text-sm text-muted-foreground">
        Ngôn ngữ: <span className="font-medium text-foreground">Python 3</span> — v1
        chỉ chấm Python, mỗi ngôn ngữ cần một image sandbox riêng.
      </p>

      <div className="flex flex-wrap items-center gap-3">
      <Button size="sm" variant={exercise === null ? "default" : "outline"} onClick={handleSave} disabled={save.isPending}>
        {save.isPending ? (
          <>
            <Loader2 className="animate-spin" aria-hidden />
            Đang lưu…
          </>
        ) : exercise === null ? (
          "Tạo bài tập"
        ) : (
          "Lưu bài tập"
        )}
      </Button>
        <p role="status" className="flex items-center gap-1.5 text-body-sm text-success-text">
          {save.isSuccess && !save.isPending ? (
            <>
              <Check className="size-4" aria-hidden />
              Đã lưu bài tập.
            </>
          ) : null}
        </p>
      </div>
    </div>
  );
}
