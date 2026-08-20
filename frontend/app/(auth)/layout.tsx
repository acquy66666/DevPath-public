import Link from "next/link";
import type { ReactNode } from "react";

/**
 * Sign-in and sign-up stand on their own page: no site header, no footer, no
 * navigation out except the logo. One form, one decision.
 */
export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-8 px-4 py-12">
      <Link href="/" className="text-2xl font-semibold tracking-tight">
        Dev<span className="text-muted-foreground">Path</span>
      </Link>
      <div className="w-full max-w-sm">{children}</div>
    </main>
  );
}
