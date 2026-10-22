"use client";

import Link from "next/link";

import { Button } from "@/components/ui/button";
import { StatePanel } from "@/components/ui/state-panel";

/**
 * A course that does not exist calls `notFound()` instead, so anything landing
 * here is the backend being unreachable or answering badly -- something a
 * retry can genuinely fix, which is why it is `retry` (fetch the page again)
 * and not `reset` (re-render the failure that is already here).
 */
export default function CourseDetailError({
  error,
  retry,
}: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  return (
    <StatePanel
      mood="sorry"
      title="Không tải được khóa học"
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
