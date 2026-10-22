"use client";

import Link from "next/link";

import { Button } from "@/components/ui/button";
import { StatePanel } from "@/components/ui/state-panel";

/**
 * Covers the catalogue. The course page one level down has its own boundary
 * with its own wording, and the nearest one wins. The list is fetched on the
 * server, so only `retry` (fetch again) can bring it back.
 */
export default function CatalogError({
  error,
  retry,
}: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  return (
    <StatePanel
      mood="sorry"
      title="Không tải được danh sách khóa học"
      detail={error.digest ? `Mã lỗi: ${error.digest}` : null}
      actions={
        <>
          <Button onClick={retry}>Thử lại</Button>
          <Button variant="outline" asChild>
            <Link href="/">Về trang chủ</Link>
          </Button>
        </>
      }
    >
      Máy chủ đang không trả lời. Thử lại sau ít phút, hoặc quay về trang chủ.
    </StatePanel>
  );
}
