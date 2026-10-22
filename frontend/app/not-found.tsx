import Link from "next/link";

import { SiteHeader } from "@/components/layout/site-header";
import { Button } from "@/components/ui/button";
import { StatePanel } from "@/components/ui/state-panel";

/**
 * Any URL that matches no route at all.
 *
 * The course pages have their own 404 with wording about slugs and drafts;
 * this one is for the address that was simply never a page. It keeps the
 * header, because a 404 without a way to navigate is a dead end -- and
 * root-level not-found renders outside every group layout, so the header has
 * to be asked for here. Naomi holds her map upside down (`lost`).
 */
export default function NotFound() {
  return (
    <>
      <SiteHeader />
      <main className="flex flex-1 items-center">
        <StatePanel
          mood="lost"
          code="404"
          title="Không có trang nào ở đây"
          actions={
            <>
              <Button asChild>
                <Link href="/">Về trang chủ</Link>
              </Button>
              <Button variant="outline" asChild>
                <Link href="/khoa-hoc">Xem khóa học</Link>
              </Button>
            </>
          }
        >
          Đường dẫn có thể gõ sai, hoặc trang đã được đổi chỗ.
        </StatePanel>
      </main>
    </>
  );
}
