import Link from "next/link";

import { Button } from "@/components/ui/button";

export function SiteHeader() {
  return (
    <header className="border-b">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4">
        <Link href="/" className="text-lg font-semibold tracking-tight">
          Dev<span className="text-muted-foreground">Path</span>
        </Link>

        {/* Điều hướng khóa học thêm ở Phase 2, khi đã có trang thật để trỏ tới. */}
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" disabled>
            Đăng nhập
          </Button>
          <Button size="sm" disabled>
            Đăng ký
          </Button>
        </div>
      </div>
    </header>
  );
}
