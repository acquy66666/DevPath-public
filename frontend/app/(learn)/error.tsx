"use client";

import Link from "next/link";

import { Button } from "@/components/ui/button";
import { StatePanel } from "@/components/ui/state-panel";

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
  retry,
}: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  return (
    <StatePanel
      mood="sorry"
      title="Không mở được bài học này"
      detail={error.digest ? `Mã lỗi: ${error.digest}` : null}
      actions={
        <>
          <Button onClick={retry}>Thử lại</Button>
          <Button variant="outline" asChild>
            <Link href="/khoa-hoc-cua-toi">Về khóa học của tôi</Link>
          </Button>
        </>
      }
    >
      Lỗi phía hệ thống khi hiển thị trang học, không phải do bạn. Tiến độ và bài nộp của bạn vẫn được lưu trên máy
      chủ.
    </StatePanel>
  );
}
