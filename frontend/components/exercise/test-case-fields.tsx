"use client";

import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

/**
 * The two boxes that make a test case, shared by the add form and the editor.
 *
 * The note under the expected output is the comparison policy from
 * `grader/runner/compare.py`, said where it matters: an instructor who knows
 * trailing spaces are forgiven does not spend an evening hunting a WA that was
 * never there.
 */
export function TestCaseFields({
  inputId,
  outputId,
  input,
  expected,
  onInputChange,
  onExpectedChange,
  disabled,
}: {
  inputId: string;
  outputId: string;
  input: string;
  expected: string;
  onInputChange: (value: string) => void;
  onExpectedChange: (value: string) => void;
  disabled: boolean;
}) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <div className="space-y-2">
        <Label htmlFor={inputId}>Đầu vào (stdin)</Label>
        <Textarea
          id={inputId}
          value={input}
          onChange={(event) => onInputChange(event.target.value)}
          rows={5}
          className="font-mono text-sm"
          placeholder={"5\n1 2 3 4 6"}
          disabled={disabled}
        />
        <p className="text-sm text-muted-foreground">
          Đúng những gì chương trình đọc từ stdin. Để trống nếu bài không có đầu
          vào.
        </p>
      </div>

      <div className="space-y-2">
        <Label htmlFor={outputId}>Đầu ra mong đợi (stdout)</Label>
        <Textarea
          id={outputId}
          value={expected}
          onChange={(event) => onExpectedChange(event.target.value)}
          rows={5}
          className="font-mono text-sm"
          placeholder="3"
          disabled={disabled}
        />
        <p className="text-sm text-muted-foreground">
          Khi chấm, hệ thống bỏ qua khoảng trắng cuối mỗi dòng và các dòng trống ở
          cuối. Khoảng trắng giữa dòng và thứ tự dòng vẫn tính.
        </p>
      </div>
    </div>
  );
}
