"use client";

import Link from "next/link";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

/**
 * The net under the room where people study.
 *
 * Failures that come back from the API are caught next to the thing that
 * failed -- a lesson that will not load, a submission that was refused -- so
 * what reaches here is a render that threw. The wording says the two things
 * that are actually true in that situation: nothing was lost, and there is a
 * way out that is not the back button.
 */
export default function LearnError({
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
          <CardTitle>Không mở được bài học này</CardTitle>
          <CardDescription>
            Có lỗi ngoài dự tính khi hiển thị trang học. Tiến độ và bài nộp của bạn
            vẫn được lưu trên máy chủ.
            {error.digest ? ` Mã lỗi: ${error.digest}.` : null}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-3">
          <Button onClick={reset}>Thử lại</Button>
          <Button variant="outline" asChild>
            <Link href="/khoa-hoc-cua-toi">Về khóa học của tôi</Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
