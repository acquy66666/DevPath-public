"use client";

import { Button } from "@/components/ui/button";
import { StatePanel } from "@/components/ui/state-panel";

/**
 * The last net under the instructor screens. Errors from API calls are caught
 * where they happen and shown next to the thing that failed; what lands here is
 * a render that threw, so the only honest offer is "thử lại". No Naomi: in the
 * work areas she only appears in empty states.
 */
export default function InstructorError({
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
      detail={error.digest ? `Mã lỗi: ${error.digest}` : null}
      actions={<Button onClick={retry}>Thử lại</Button>}
    >
      Lỗi phía hệ thống khi hiển thị khu vực giảng viên, không phải do bạn. Nội dung đã lưu không bị ảnh hưởng.
    </StatePanel>
  );
}
