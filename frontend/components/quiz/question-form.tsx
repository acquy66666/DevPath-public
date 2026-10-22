"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, X } from "lucide-react";
import { useId, useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { apiErrorMessage } from "@/lib/api/error-messages";
import {
  addQuestion,
  updateQuestion,
  type Question,
} from "@/lib/api/quiz-authoring";
import { useAuth } from "@/lib/auth/auth-provider";
import { cn } from "@/lib/utils";

/** The backend's own limits, repeated here so the form can enforce them. */
const MIN_OPTIONS = 2;
const MAX_OPTIONS = 6;

/**
 * Write one question, or edit one that exists.
 *
 * The correct answer is chosen with the same radio the student will use,
 * against the same list — an author picks the right answer by pointing at it
 * rather than by typing an index, because an index is a thing you can get
 * wrong silently.
 */
export function QuestionForm({
  quizId,
  question,
  onDone,
}: {
  quizId: string;
  /** The question being edited, or null to write a new one. */
  question: Question | null;
  onDone: () => void;
}) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const fieldId = useId();

  const [text, setText] = useState(question?.question ?? "");
  const [options, setOptions] = useState<string[]>(question?.options ?? ["", ""]);
  const [correct, setCorrect] = useState(question?.correct_index ?? 0);
  const [explanation, setExplanation] = useState(question?.explanation ?? "");

  const save = useMutation({
    mutationFn: async () => {
      const input = {
        question: text.trim(),
        options: options.map((option) => option.trim()),
        correct_index: correct,
        explanation: explanation.trim() || null,
      };
      const token = accessToken as string;
      return question
        ? updateQuestion(token, question.id, input)
        : addQuestion(token, quizId, input);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["quiz-questions", quizId] });
      queryClient.invalidateQueries({ queryKey: ["quiz"] });
      onDone();
    },
  });

  const filled = text.trim().length > 0 && options.every((option) => option.trim());

  return (
    <form
      className="space-y-4 rounded-md border p-4"
      onSubmit={(event) => {
        event.preventDefault();
        save.mutate();
      }}
    >
      <div className="space-y-2">
        <Label htmlFor={`${fieldId}-question`}>Câu hỏi</Label>
        <Textarea
          id={`${fieldId}-question`}
          value={text}
          onChange={(event) => setText(event.target.value)}
          rows={2}
          placeholder="Ví dụ: Hàm len() trong Python trả về gì?"
        />
      </div>

      <fieldset className="space-y-2">
        <legend className="text-sm font-medium">
          Phương án — chọn ô tròn ở đáp án đúng
        </legend>
        {options.map((option, index) => (
          <div key={index} className="flex items-center gap-2">
            <input
              type="radio"
              name={`${fieldId}-correct`}
              className="size-4 shrink-0"
              checked={correct === index}
              onChange={() => setCorrect(index)}
              aria-label={`Phương án ${index + 1} là đáp án đúng`}
            />
            <Input
              value={option}
              onChange={(event) =>
                setOptions((current) =>
                  current.map((value, position) =>
                    position === index ? event.target.value : value,
                  ),
                )
              }
              placeholder={`Phương án ${index + 1}`}
              className={cn(correct === index && "border-primary")}
            />
            <Button
              type="button"
              variant="ghost"
              size="icon"
              disabled={options.length <= MIN_OPTIONS}
              onClick={() => {
                setOptions((current) => current.filter((_, position) => position !== index));
                // Removing the option that was marked correct, or one before
                // it, would otherwise leave the mark pointing at a different
                // answer than the one the author chose.
                setCorrect((current) => {
                  if (current === index) return 0;
                  return current > index ? current - 1 : current;
                });
              }}
              aria-label={`Xóa phương án ${index + 1}`}
            >
              <X className="size-4" />
            </Button>
          </div>
        ))}

        {options.length < MAX_OPTIONS ? (
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setOptions((current) => [...current, ""])}
          >
            <Plus className="mr-1 size-4" />
            Thêm phương án
          </Button>
        ) : null}
      </fieldset>

      <div className="space-y-2">
        <Label htmlFor={`${fieldId}-explanation`}>Giải thích (học viên đọc sau khi nộp)</Label>
        <Textarea
          id={`${fieldId}-explanation`}
          value={explanation}
          onChange={(event) => setExplanation(event.target.value)}
          rows={2}
          placeholder="Vì sao đáp án đó đúng."
        />
      </div>

      {save.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(save.error)}</AlertDescription>
        </Alert>
      ) : null}

      <div className="flex gap-2">
        <Button type="submit" disabled={!filled || save.isPending}>
          {question ? "Lưu câu hỏi" : "Thêm câu hỏi"}
        </Button>
        <Button type="button" variant="ghost" onClick={onDone}>
          Hủy
        </Button>
      </div>
    </form>
  );
}
