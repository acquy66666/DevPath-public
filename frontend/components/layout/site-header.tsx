"use client";

import { Menu } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { UserMenu } from "@/components/auth/user-menu";
import { CartBadge } from "@/components/commerce/cart-badge";
import { BrandMark } from "@/components/layout/brand-mark";
import { NotificationBell } from "@/components/notifications/notification-bell";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/lib/auth/auth-provider";
import { cn } from "@/lib/utils";

/** The site's sections, for everyone. A signed-in user's own pages live in the avatar menu. */
const NAV = [
  { href: "/khoa-hoc", label: "Khóa học" },
  { href: "/bang-xep-hang", label: "Bảng xếp hạng" },
] as const;

function isCurrent(pathname: string, href: string) {
  // "/khoa-hoc-cua-toi" starts with "/khoa-hoc" and is not under it.
  return pathname === href || pathname.startsWith(`${href}/`);
}

/**
 * Client Component because the session lives in context, and the session is
 * only known in the browser: the access token is held in memory and restored
 * from the refresh cookie after mount, so the server has nothing to render.
 * `status === "loading"` is that gap -- a placeholder of the same size keeps
 * the header from jumping when the answer arrives.
 *
 * Below `md` the section links fold into a menu button, which is what lets
 * the logo and both sign-in buttons share a 360px phone at their design-system
 * size. From `sm` up the type is a step larger than a form's: the header is
 * read off a projector during a demo.
 */
export function SiteHeader() {
  const { user, status } = useAuth();
  const pathname = usePathname();

  return (
    <header className="border-b bg-card print:hidden">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-2 px-4">
        <div className="flex min-w-0 items-center gap-1 md:gap-6">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="md:hidden" aria-label="Mở menu điều hướng">
                <Menu className="size-5" aria-hidden />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-56">
              {NAV.map((item) => (
                <DropdownMenuItem key={item.href} asChild>
                  <Link
                    href={item.href}
                    aria-current={isCurrent(pathname, item.href) ? "page" : undefined}
                    className="min-h-10 text-base aria-[current=page]:bg-secondary aria-[current=page]:font-semibold aria-[current=page]:text-secondary-foreground"
                  >
                    {item.label}
                  </Link>
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>

          <Link href="/" className="shrink-0 rounded-md text-xl font-bold sm:text-2xl">
            <BrandMark />
          </Link>

          <nav aria-label="Điều hướng chính" className="hidden items-center gap-1 md:flex">
            {NAV.map((item) => {
              const current = isCurrent(pathname, item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={current ? "page" : undefined}
                  className={cn(
                    "inline-flex h-10 items-center rounded-md px-3 text-base font-semibold whitespace-nowrap transition-colors",
                    current
                      ? "bg-secondary text-secondary-foreground"
                      : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                  )}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>

        <div className="flex shrink-0 items-center gap-1 sm:gap-2">
          {status === "loading" ? (
            <Skeleton className="h-9 w-36 sm:h-11 sm:w-52" />
          ) : user ? (
            <>
              <NotificationBell />
              <CartBadge />
              <UserMenu user={user} />
            </>
          ) : (
            <>
              <Button variant="ghost" size="sm" className="sm:h-11 sm:px-5 sm:text-base" asChild>
                <Link href="/dang-nhap">Đăng nhập</Link>
              </Button>
              <Button size="sm" className="sm:h-11 sm:px-5 sm:text-base" asChild>
                <Link href="/dang-ky">Đăng ký</Link>
              </Button>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
