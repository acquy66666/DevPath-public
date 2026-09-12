import Link from "next/link";

import { Button } from "@/components/ui/button";
import { SiteHeader } from "@/components/layout/site-header";

/**
 * Any URL that matches no route at all.
 *
 * The course pages have their own 404 with wording about slugs and drafts;
 * this one is for the address that was simply never a page. It keeps the
 * header, because a 404 without a way to navigate is a dead end -- and
 * root-level not-found renders outside every group layout, so the header has
 * to be asked for here.
 */
export default function NotFound() {
  return (
    <>
      <SiteHeader />
      <main className="mx-auto max-w-md flex-1 px-4 py-20 text-center">
        <p className="text-sm font-medium text-muted-foreground">404</p>
        <h1 className="mt-1 text-xl font-semibold tracking-tight">
          Không có trang nào ở đây
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Đường dẫn có thể gõ sai, hoặc trang đã được đổi chỗ.
        </p>

        <div className="mt-6 flex flex-wrap justify-center gap-3">
          <Button asChild>
            <Link href="/">Về trang chủ</Link>
          </Button>
          <Button variant="outline" asChild>
            <Link href="/khoa-hoc">Xem khóa học</Link>
          </Button>
        </div>
      </main>
    </>
  );
}
