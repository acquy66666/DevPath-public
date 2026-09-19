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
 */
export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <main className="relative flex flex-1 flex-col items-center justify-center gap-8 px-4 py-16">
      <Link
        href="/"
        className="absolute top-4 left-4 inline-flex items-center gap-1.5 rounded-md px-2 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none sm:top-6 sm:left-6"
      >
        <ArrowLeft className="size-4" aria-hidden />
        Về trang chủ
      </Link>

      <Link
        href="/"
        aria-label="DevPath — về trang chủ"
        className="text-2xl font-semibold tracking-tight transition-opacity hover:opacity-70"
      >
        Dev<span className="text-muted-foreground">Path</span>
      </Link>
      <div className="w-full max-w-sm">{children}</div>
    </main>
  );
}
