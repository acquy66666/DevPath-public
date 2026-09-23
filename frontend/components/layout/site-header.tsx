"use client";

import Link from "next/link";

import { UserMenu } from "@/components/auth/user-menu";
import { CartBadge } from "@/components/commerce/cart-badge";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth/auth-provider";

/**
 * Client Component because the session lives in context, and the session is
 * only known in the browser: the access token is held in memory and restored
 * from the refresh cookie after mount, so the server has nothing to render.
 * `status === "loading"` is that gap -- a placeholder of the same size keeps
 * the header from jumping when the answer arrives.
 */
export function SiteHeader() {
  const { user, status } = useAuth();

  return (
    <header className="border-b">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4">
        <div className="flex items-center gap-6">
          <Link href="/" className="text-[1.575rem] font-semibold tracking-tight">
            Dev<span className="text-muted-foreground">Path</span>
          </Link>
          <Link
            href="/khoa-hoc"
            className="text-[1.225rem] text-muted-foreground transition-colors hover:text-foreground"
          >
            Khóa học
          </Link>
        </div>

        <div className="flex items-center gap-2">
          {status === "loading" ? (
            <div className="h-8 w-32 animate-pulse rounded-md bg-muted" aria-hidden />
          ) : user ? (
            <>
              <CartBadge />
              <UserMenu user={user} />
            </>
          ) : (
            <>
              <Button variant="ghost" size="sm" className="text-[1.12rem] h-10 px-4" asChild>
                <Link href="/dang-nhap">Đăng nhập</Link>
              </Button>
              <Button size="sm" className="text-[1.12rem] h-10 px-4" asChild>
                <Link href="/dang-ky">Đăng ký</Link>
              </Button>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
