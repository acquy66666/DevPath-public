"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Plus, TriangleAlert } from "lucide-react";
import { useId, useState, type FormEvent } from "react";

import { TestCaseFields } from "@/components/exercise/test-case-fields";
import { TestCaseRow } from "@/components/exercise/test-case-row";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiErrorMessage } from "@/lib/api/error-messages";
import {
  createTestCase,
  listTestCases,
  reorderTestCases,
  type TestCase,
} from "@/lib/api/grading";
import { useAuth } from "@/lib/auth/auth-provider";
import { validateScoreWeight } from "@/lib/grading/validation";

const NO_CASES: TestCase[] = [];

/**
 * The test cases of one exercise, in the order they are marked in.
 *
 * Order is part of the interface rather than decoration: a result that says
 * “test case 3 failed” refers to the third row here, so moving one is a real
 * change and goes to the server as the whole arrangement.
 */
export function TestCaseManager({ exerciseId }: { exerciseId: string }) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const queryKey = ["test-cases", exerciseId];

  const query = useQuery({
    queryKey,
    queryFn: () => listTestCases(accessToken as string, exerciseId),
    enabled: accessToken !== null,
  });

  const cases = query.data ?? NO_CASES;

  const order = useMutation({
    mutationFn: (testCaseIds: string[]) =>
      reorderTestCases(accessToken as string, exerciseId, testCaseIds),
    onSuccess: (updated) => queryClient.setQueryData(queryKey, updated),
    // Whatever happened, the server's numbering is the one that counts.
    onSettled: () => queryClient.invalidateQueries({ queryKey }),
  });

  function move(from: number, to: number) {
    if (to < 0 || to >= cases.length) return;

    const next = [...cases];
    const [moved] = next.splice(from, 1);
    next.splice(to, 0, moved);

    // Shown moved straight away; the mutation's onSettled brings back whatever
    // the server actually stored.
    queryClient.setQueryData(queryKey, next);
    order.mutate(next.map((testCase) => testCase.id));
  }

  const samples = cases.filter((testCase) => !testCase.is_hidden).length;
  const totalWeight = cases.reduce(
    (sum, testCase) => sum + testCase.score_weight,
    0,
  );

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h4 className="font-medium">Test case</h4>
        {cases.length > 0 ? (
          <p className="text-sm text-muted-foreground">
            {cases.length} test case · {samples} mẫu, {cases.length - samples} ẩn ·
            tổng trọng số {totalWeight}
          </p>
        ) : null}
      </div>

      {order.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(order.error)}</AlertDescription>
        </Alert>
      ) : null}

      {query.isPending ? (
        <div className="h-20 animate-pulse rounded-md bg-muted/40" />
      ) : query.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(query.error)}</AlertDescription>
        </Alert>
      ) : (
        <>
          <Warnings cases={cases} samples={samples} />

          {cases.length > 0 ? (
            <ul className="space-y-2">
              {cases.map((testCase, index) => (
                <TestCaseRow
                  key={testCase.id}
                  testCase={testCase}
                  exerciseId={exerciseId}
                  index={index}
                  total={cases.length}
                  onMove={move}
                  isMoving={order.isPending}
                />
              ))}
            </ul>
          ) : null}

          <AddTestCaseForm exerciseId={exerciseId} />
        </>
      )}
    </section>
  );
}

/**
 * The three states an exercise can be in that no error message would catch.
 *
 * Each is legal at the API level and wrong as teaching: nothing to mark
 * against, nothing to debug against, or nothing to hide.
 */
function Warnings({ cases, samples }: { cases: TestCase[]; samples: number }) {
  if (cases.length === 0) {
    return (
      <Alert variant="destructive">
        <TriangleAlert className="size-4" aria-hidden />
        <AlertDescription>
          Bài tập chưa có test case nào nên hệ thống từ chối nhận bài nộp — không
          có gì để chấm. Thêm ít nhất một test case mẫu và một test case ẩn.
        </AlertDescription>
      </Alert>
    );
  }

  if (samples === 0) {
    return (
      <Alert>
        <TriangleAlert className="size-4" aria-hidden />
        <AlertDescription>
          Mọi test case đều ẩn. Học viên không có ví dụ nào để thử trước khi nộp,
          nên sai là sai trong bóng tối — nên để lộ ít nhất một case làm mẫu.
        </AlertDescription>
      </Alert>
    );
  }

  if (samples === cases.length) {
    return (
      <Alert>
        <TriangleAlert className="size-4" aria-hidden />
        <AlertDescription>
          Mọi test case đều hiển thị. Chỉ cần in đúng đáp án mẫu là qua bài mà
          không cần giải — thêm vài case ẩn để bài tập có chỗ kiểm tra thật.
        </AlertDescription>
      </Alert>
    );
  }

  return null;
}

function AddTestCaseForm({ exerciseId }: { exerciseId: string }) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const inputId = useId();
  const outputId = useId();
  const hiddenId = useId();
  const weightId = useId();

  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [expected, setExpected] = useState("");
  // Hidden by default, like the column behind it: forgetting to think about it
  // gives nothing away, and revealing a case has to be a decision.
  const [isHidden, setIsHidden] = useState(true);
  const [weight, setWeight] = useState("1");
  const [weightError, setWeightError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () =>
      createTestCase(accessToken as string, exerciseId, {
        input,
        expected_output: expected,
        is_hidden: isHidden,
        score_weight: Number(weight.trim()),
      }),
    onSuccess: () => {
      setInput("");
      setExpected("");
      setWeight("1");
      // Back to hidden, not to whatever was used last: the cost of forgetting
      // this box is an answer key on the page, so the safe value is the one
      // that has to be argued for every time.
      setIsHidden(true);
      queryClient.invalidateQueries({ queryKey: ["test-cases", exerciseId] });
    },
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const error = validateScoreWeight(weight);
    setWeightError(error);
    if (error) return;
    create.mutate();
  }

  if (!open) {
    return (
      <Button variant="ghost" size="sm" onClick={() => setOpen(true)}>
        <Plus aria-hidden />
        Thêm test case
      </Button>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3 rounded-md border p-3" noValidate>
      {create.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(create.error)}</AlertDescription>
        </Alert>
      ) : null}

      <TestCaseFields
        inputId={inputId}
        outputId={outputId}
        input={input}
        expected={expected}
        onInputChange={setInput}
        onExpectedChange={setExpected}
        disabled={create.isPending}
      />

      <div className="flex flex-wrap items-end gap-4">
        <div className="flex items-start gap-2">
          <input
            id={hiddenId}
            type="checkbox"
            checked={isHidden}
            onChange={(event) => setIsHidden(event.target.checked)}
            disabled={create.isPending}
            className="mt-1 size-4 rounded border-input accent-primary"
          />
          <div>
            <Label htmlFor={hiddenId}>Ẩn với học viên</Label>
            <p className="text-sm text-muted-foreground">
              Case ẩn chỉ trả về verdict; đầu vào và đáp án không bao giờ rời máy
              chủ.
            </p>
          </div>
        </div>

        <div className="space-y-1">
          <Label htmlFor={weightId}>Trọng số</Label>
          <Input
            id={weightId}
            value={weight}
            onChange={(event) => setWeight(event.target.value)}
            inputMode="numeric"
            aria-invalid={Boolean(weightError)}
            disabled={create.isPending}
            className="w-24"
          />
        </div>
      </div>

      {weightError ? <p className="text-sm text-destructive">{weightError}</p> : null}

      <div className="flex gap-2">
        <Button type="submit" size="sm" disabled={create.isPending}>
          {create.isPending ? (
            <>
              <Loader2 className="animate-spin" aria-hidden />
              Đang thêm…
            </>
          ) : (
            "Thêm test case"
          )}
        </Button>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          onClick={() => {
            setOpen(false);
            setWeightError(null);
          }}
          disabled={create.isPending}
        >
          Đóng
        </Button>
      </div>
    </form>
  );
}
