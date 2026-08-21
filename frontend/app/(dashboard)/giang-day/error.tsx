"use client";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

/**
 * The last net under the instructor screens. Errors from API calls are caught
 * where they happen and shown next to the thing that failed; what lands here is
 * a render that threw, so the only honest offer is "thử lại".
 */
export default function InstructorError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="mx-auto max-w-xl px-4 py-12">
      <Card>
        <CardHeader>
          <CardTitle>Không mở được trang này</CardTitle>
          <CardDescription>
            Có lỗi ngoài dự tính khi hiển thị khu vực giảng viên.
            {error.digest ? ` Mã lỗi: ${error.digest}.` : null}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button onClick={reset}>Thử lại</Button>
        </CardContent>
      </Card>
    </div>
  );
}
