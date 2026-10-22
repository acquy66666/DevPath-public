"use client";

import Link from "next/link";

import { Button } from "@/components/ui/button";
import { StatePanel } from "@/components/ui/state-panel";

/**
 * The last net, under every route that has not put up one of its own.
 *
 * Without this file a render that throws anywhere outside the three groups
 * that do have a boundary lands on Next's built-in error page: English, and
 * with nothing on it but the word "error". A demo does not get to choose which
 * page breaks in front of the audience.
 *
 * `retry` (Next 16.3) fetches the segment again before rendering it; the older
 * `reset` only re-renders what is already on the client, so a page whose
 * server render failed stayed broken however often "Thử lại" was pressed.
 */
export default function AppError({
  error,
  retry,
}: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  return (
    <main className="flex flex-1 items-center">
      <StatePanel
        mood="sorry"
        title="Trang này đang gặp lỗi"
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
        Lỗi phía hệ thống, không phải do bạn. Thử lại thường là đủ; nếu vẫn vậy, về trang chủ rồi vào lại.
      </StatePanel>
    </main>
  );
}
