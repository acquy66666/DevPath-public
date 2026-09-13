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
 * The last net, under every route that has not put up one of its own.
 *
 * Without this file a render that throws anywhere outside the three groups
 * that do have a boundary lands on Next's built-in error page: English, and
 * with nothing on it but the word "error". A demo does not get to choose which
 * page breaks in front of the audience.
 */
export default function AppError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="mx-auto flex min-h-[60vh] max-w-xl items-center px-4 py-12">
      <Card className="w-full">
        <CardHeader>
          <CardTitle>Có gì đó hỏng rồi</CardTitle>
          <CardDescription>
            Trang này gặp lỗi ngoài dự tính. Thử lại thường là đủ; nếu vẫn vậy thì
            quay về trang chủ rồi vào lại.
            {error.digest ? ` Mã lỗi: ${error.digest}.` : null}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-3">
          <Button onClick={reset}>Thử lại</Button>
          <Button variant="outline" asChild>
            <Link href="/">Về trang chủ</Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
