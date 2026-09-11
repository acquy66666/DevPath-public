"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, ChevronUp, Loader2, Pencil, Trash2 } from "lucide-react";
import { useId, useState } from "react";

import { TestCaseFields } from "@/components/exercise/test-case-fields";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { deleteTestCase, updateTestCase, type TestCase } from "@/lib/api/grading";
import { useAuth } from "@/lib/auth/auth-provider";
import { validateScoreWeight } from "@/lib/grading/validation";

const PREVIEW_LIMIT = 24;

/**
 * A value squeezed onto one line.
 *
 * Line breaks become a visible mark rather than disappearing: most test inputs
 * start with a count, so “first line only” would print the same “5” on every
 * row and the list would say nothing about what the cases are.
 */
function preview(value: string): string {
  const text = value
    .split("\n")
    .filter((line) => line.length > 0)
    .join(" ⏎ ");

  if (!text) return "(trống)";
  return text.length > PREVIEW_LIMIT ? `${text.slice(0, PREVIEW_LIMIT)}…` : text;
}

export function TestCaseRow({
  testCase,
  exerciseId,
  index,
  total,
  onMove,
  isMoving,
}: {
  testCase: TestCase;
  exerciseId: string;
  index: number;
  total: number;
  onMove: (from: number, to: number) => void;
  isMoving: boolean;
}) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  const remove = useMutation({
    mutationFn: () => deleteTestCase(accessToken as string, testCase.id),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["test-cases", exerciseId] }),
  });

  return (
    <li className="rounded-lg border bg-background">
      <div className="flex flex-wrap items-center gap-2 p-2">
        <span className="w-6 shrink-0 text-center text-sm text-muted-foreground">
          {index + 1}
        </span>

        <Badge
          variant={testCase.is_hidden ? "secondary" : "outline"}
          className="shrink-0"
        >
          {testCase.is_hidden ? "Ẩn" : "Mẫu"}
        </Badge>

        <code className="min-w-0 flex-1 truncate font-mono text-xs text-muted-foreground">
          {preview(testCase.input)} → {preview(testCase.expected_output)}
        </code>

        <span className="shrink-0 text-xs text-muted-foreground">
          trọng số {testCase.score_weight}
        </span>

        <Button
          size="icon"
          variant="ghost"
          onClick={() => onMove(index, index - 1)}
          disabled={index === 0 || isMoving}
          aria-label={`Đưa test case ${index + 1} lên trên`}
        >
          <ChevronUp aria-hidden />
        </Button>
        <Button
          size="icon"
          variant="ghost"
          onClick={() => onMove(index, index + 1)}
          disabled={index === total - 1 || isMoving}
          aria-label={`Đưa test case ${index + 1} xuống dưới`}
        >
          <ChevronDown aria-hidden />
        </Button>
        <Button
          size="icon"
          variant="ghost"
          onClick={() => setOpen((current) => !current)}
          aria-expanded={open}
          aria-label={`Sửa test case ${index + 1}`}
        >
          <Pencil aria-hidden />
        </Button>
        <Button
          size="icon"
          variant="ghost"
          onClick={() => setConfirmingDelete(true)}
          aria-label={`Xóa test case ${index + 1}`}
        >
          <Trash2 aria-hidden />
        </Button>
      </div>

      {confirmingDelete ? (
        <div className="flex flex-wrap items-center gap-2 border-t bg-destructive/5 px-3 py-2">
          <span className="text-sm">Xóa test case này?</span>
          <Button
            size="sm"
            variant="destructive"
            onClick={() => remove.mutate()}
            disabled={remove.isPending}
          >
            {remove.isPending ? (
              <>
                <Loader2 className="animate-spin" aria-hidden />
                Đang xóa…
              </>
            ) : (
              "Xóa"
            )}
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setConfirmingDelete(false)}
            disabled={remove.isPending}
          >
            Hủy
          </Button>
        </div>
      ) : null}

      {remove.isError ? (
        <div className="px-3 pb-3">
          <Alert variant="destructive">
            <AlertDescription>{apiErrorMessage(remove.error)}</AlertDescription>
          </Alert>
        </div>
      ) : null}

      {open ? (
        // Keyed by the row so the fields are seeded by mounting rather than by
        // an effect that would fight with whatever is half-typed.
        <TestCaseEditor
          key={testCase.id}
          testCase={testCase}
          exerciseId={exerciseId}
          onClose={() => setOpen(false)}
        />
      ) : null}
    </li>
  );
}

function TestCaseEditor({
  testCase,
  exerciseId,
  onClose,
}: {
  testCase: TestCase;
  exerciseId: string;
  onClose: () => void;
}) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const inputId = useId();
  const outputId = useId();
  const hiddenId = useId();
  const weightId = useId();

  const [input, setInput] = useState(testCase.input);
  const [expected, setExpected] = useState(testCase.expected_output);
  const [isHidden, setIsHidden] = useState(testCase.is_hidden);
  const [weight, setWeight] = useState(String(testCase.score_weight));
  const [weightError, setWeightError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: () =>
      updateTestCase(accessToken as string, testCase.id, {
        input,
        expected_output: expected,
        is_hidden: isHidden,
        score_weight: Number(weight.trim()),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["test-cases", exerciseId] });
      onClose();
    },
  });

  return (
    <div className="space-y-3 border-t bg-muted/20 p-3">
      {save.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(save.error)}</AlertDescription>
        </Alert>
      ) : null}

      <TestCaseFields
        inputId={inputId}
        outputId={outputId}
        input={input}
        expected={expected}
        onInputChange={setInput}
        onExpectedChange={setExpected}
        disabled={save.isPending}
      />

      <div className="flex flex-wrap items-end gap-4">
        <div className="flex items-start gap-2">
          <input
            id={hiddenId}
            type="checkbox"
            checked={isHidden}
            onChange={(event) => setIsHidden(event.target.checked)}
            disabled={save.isPending}
            className="mt-1 size-4 rounded border-input accent-primary"
          />
          <Label htmlFor={hiddenId}>Ẩn với học viên</Label>
        </div>

        <div className="space-y-1">
          <Label htmlFor={weightId}>Trọng số</Label>
          <Input
            id={weightId}
            value={weight}
            onChange={(event) => setWeight(event.target.value)}
            inputMode="numeric"
            aria-invalid={Boolean(weightError)}
            disabled={save.isPending}
            className="w-24"
          />
        </div>
      </div>

      {weightError ? <p className="text-sm text-destructive">{weightError}</p> : null}

      <div className="flex gap-2">
        <Button
          size="sm"
          onClick={() => {
            const error = validateScoreWeight(weight);
            setWeightError(error);
            if (error) return;
            save.mutate();
          }}
          disabled={save.isPending}
        >
          {save.isPending ? (
            <>
              <Loader2 className="animate-spin" aria-hidden />
              Đang lưu…
            </>
          ) : (
            "Lưu test case"
          )}
        </Button>
        <Button size="sm" variant="ghost" onClick={onClose} disabled={save.isPending}>
          Đóng
        </Button>
      </div>
    </div>
  );
}
