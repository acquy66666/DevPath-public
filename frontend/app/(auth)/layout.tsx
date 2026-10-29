import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

/**
 * Sign-in and sign-up stand on their own page: no site header, no footer.
 * One form, one decision.
 *
 * But not a dead end. The logo always led home, and nobody could tell --
 * it reads as a title, not as a link. Someone who opened this page by
 * mistake, or changed their mind, gets a way out that says what it does.
 * The privacy policy stays one click away too: it is what an account agrees to.
 */
export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <main id="noi-dung" className="flex flex-1 flex-col items-center gap-6 px-4 pt-4 pb-10 sm:gap-8 sm:pt-6">
      <div className="flex w-full">
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 rounded-md px-2 py-1.5 text-body-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        >
          <ArrowLeft className="size-4" aria-hidden />
          Về trang chủ
        </Link>
      </div>

      <div className="flex w-full flex-1 flex-col items-center justify-center">{children}</div>

      <Link
        href="/chinh-sach-bao-mat"
        className="text-caption text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
      >
        Chính sách bảo mật
      </Link>
    </main>
  );
}
