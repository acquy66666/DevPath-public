"use client";

import Link from "next/link";

import { UserMenu } from "@/components/auth/user-menu";
import { CartBadge } from "@/components/commerce/cart-badge";
import { NotificationBell } from "@/components/notifications/notification-bell";
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
    <header className="border-b print:hidden">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4">
        <div className="flex items-center gap-2.5 sm:gap-6">
          <Link href="/" className="text-xl font-semibold tracking-tight sm:text-[1.575rem]">
            Dev<span className="text-muted-foreground">Path</span>
          </Link>
          <Link
            href="/khoa-hoc"
            className="text-[0.9375rem] whitespace-nowrap text-muted-foreground transition-colors hover:text-foreground sm:text-[1.225rem]"
          >
            Khóa học
          </Link>
        </div>

        {/* Tighter below `sm`: bell, cart and avatar next to the logo and
            "Khóa học" only just fit a 360px phone -- and so do the two
            sign-in buttons, once their type steps down a size there. */}
        <div className="flex items-center gap-1 sm:gap-2">
          {status === "loading" ? (
            <div className="h-8 w-32 animate-pulse rounded-md bg-muted" aria-hidden />
          ) : user ? (
            <>
              <NotificationBell />
              <CartBadge />
              <UserMenu user={user} />
            </>
          ) : (
            <>
              <Button
                variant="ghost"
                size="sm"
                className="h-9 px-2 sm:h-10 sm:px-4 sm:text-[1.12rem]"
                asChild
              >
                <Link href="/dang-nhap">Đăng nhập</Link>
              </Button>
              <Button
                size="sm"
                className="h-9 px-3 sm:h-10 sm:px-4 sm:text-[1.12rem]"
                asChild
              >
                <Link href="/dang-ky">Đăng ký</Link>
              </Button>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
