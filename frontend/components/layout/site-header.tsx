"use client";

import Link from "next/link";

import { UserMenu } from "@/components/auth/user-menu";
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
        <Link href="/" className="text-lg font-semibold tracking-tight">
          Dev<span className="text-muted-foreground">Path</span>
        </Link>

        {/* Điều hướng khóa học thêm khi có trang danh sách khóa học thật. */}
        <div className="flex items-center gap-2">
          {status === "loading" ? (
            <div className="h-8 w-32 animate-pulse rounded-md bg-muted" aria-hidden />
          ) : user ? (
            <UserMenu user={user} />
          ) : (
            <>
              <Button variant="ghost" size="sm" asChild>
                <Link href="/dang-nhap">Đăng nhập</Link>
              </Button>
              <Button size="sm" asChild>
                <Link href="/dang-ky">Đăng ký</Link>
              </Button>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
