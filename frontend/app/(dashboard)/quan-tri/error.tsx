"use client";

import { Button } from "@/components/ui/button";
import { StatePanel } from "@/components/ui/state-panel";

/**
 * A render that threw. Failed API calls are shown where they happen. No
 * Naomi: in the admin area she only appears in empty states.
 */
export default function AdminError({
  error,
  retry,
}: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  return (
    <StatePanel
      mood={null}
      title="Không mở được trang này"
      titleAs="h2"
      compact
      className="mx-0"
      detail={error.digest ? `Mã lỗi: ${error.digest}` : null}
      actions={<Button onClick={retry}>Thử lại</Button>}
    >
      Lỗi phía hệ thống khi hiển thị khu vực quản trị, không phải do bạn.
    </StatePanel>
  );
}
