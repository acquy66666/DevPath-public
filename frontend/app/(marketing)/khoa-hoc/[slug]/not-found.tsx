import Link from "next/link";

import { Button } from "@/components/ui/button";

/**
 * Shown for a slug with no course behind it — mistyped, renamed, or taken down.
 *
 * A draft lands here too: the page renders anonymously, so an unpublished
 * course is 404 rather than 403, and this text has to be true for both without
 * confirming that anything exists.
 */
export default function CourseNotFound() {
  return (
    <div className="mx-auto max-w-md px-4 py-20 text-center">
      <h1 className="text-xl font-semibold tracking-tight">Không tìm thấy khóa học</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Đường dẫn có thể sai, hoặc khóa học chưa được xuất bản.
      </p>

      <div className="mt-6">
        <Button asChild>
          <Link href="/">Về trang chủ</Link>
        </Button>
      </div>
    </div>
  );
}
