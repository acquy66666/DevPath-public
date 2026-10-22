import Link from "next/link";

import { Button } from "@/components/ui/button";
import { StatePanel } from "@/components/ui/state-panel";

/**
 * Shown for a slug with no course behind it — mistyped, renamed, or taken down.
 *
 * A draft lands here too: the page renders anonymously, so an unpublished
 * course is 404 rather than 403, and this text has to be true for both without
 * confirming that anything exists.
 */
export default function CourseNotFound() {
  return (
    <StatePanel
      mood="lost"
      code="404"
      title="Không tìm thấy khóa học"
      actions={
        <>
          <Button asChild>
            <Link href="/khoa-hoc">Xem các khóa học</Link>
          </Button>
          <Button variant="outline" asChild>
            <Link href="/">Về trang chủ</Link>
          </Button>
        </>
      }
    >
      Đường dẫn có thể sai, hoặc khóa học chưa được xuất bản.
    </StatePanel>
  );
}
