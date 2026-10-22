"use client";

import Link from "next/link";

import { Button } from "@/components/ui/button";
import { StatePanel } from "@/components/ui/state-panel";

/**
 * A code that is not a certificate calls `notFound()` instead, so anything landing
 * here is the backend being unreachable or answering badly -- something a
 * retry can genuinely fix, by fetching the page again (`retry`).
 */
export default function CertificateError({
  error,
  retry,
}: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  return (
    <StatePanel
      mood="sorry"
      title="Không tải được chứng chỉ"
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
