"use client";

import Link from "next/link";

import { Button } from "@/components/ui/button";

/**
 * Covers the catalogue. The course page one level down has its own boundary
 * with its own wording, and the nearest one wins.
 */
export default function CatalogError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="mx-auto max-w-md px-4 py-20 text-center">
      <h1 className="text-xl font-semibold tracking-tight">
        Không tải được danh sách khóa học
      </h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Máy chủ đang không trả lời. Thử lại sau ít phút, hoặc quay về trang chủ.
      </p>

      <div className="mt-6 flex justify-center gap-3">
        <Button onClick={reset}>Thử lại</Button>
        <Button variant="outline" asChild>
          <Link href="/">Về trang chủ</Link>
        </Button>
      </div>
    </div>
  );
}
