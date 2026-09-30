"use client";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

/** A render that threw. Failed API calls are shown where they happen. */
export default function AdminError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Không mở được trang này</CardTitle>
        <CardDescription>
          Có lỗi ngoài dự tính khi hiển thị khu vực quản trị.
          {error.digest ? ` Mã lỗi: ${error.digest}.` : null}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Button onClick={reset}>Thử lại</Button>
      </CardContent>
    </Card>
  );
}
