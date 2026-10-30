"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { lazy, Suspense, useState } from "react";

import { CartBadge } from "@/components/commerce/cart-badge";
import { BrandMark } from "@/components/layout/brand-mark";
import { AccountButton, BellButton, MobileNavButton } from "@/components/layout/header-buttons";
import { isCurrent, NAV } from "@/components/layout/site-nav";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/lib/auth/auth-provider";
import { useAfterLoad } from "@/lib/design/use-after-load";
import { cn } from "@/lib/utils";

// The three menus load after the page is up (see header-buttons.tsx): the
// phone menu once the page has loaded and gone quiet, or at the first touch
// of its button -- the server draws the button -- and the other two only for
// a signed-in user, who is known after the session is restored. Each shows
// its own button meanwhile.
const MobileNav = dynamic(() => import("@/components/layout/mobile-nav").then((m) => m.MobileNav), {
  ssr: false,
  loading: () => <MobileNavButton />,
});
const NotificationBell = lazy(() =>
  import("@/components/notifications/notification-bell").then((m) => ({ default: m.NotificationBell })),
);
const UserMenu = lazy(() => import("@/components/auth/user-menu").then((m) => ({ default: m.UserMenu })));

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
  const menu = useAfterLoad();
  // What the reader did to the stand-in before the menu was here.
  const [early, setEarly] = useState<"open" | "focus" | null>(null);

  return (
    <header className="border-b bg-card print:hidden">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-2 px-4">
        <div className="flex min-w-0 items-center gap-1 md:gap-6">
          {menu.ready ? (
            <MobileNav defaultOpen={early === "open"} autoFocus={early !== null} />
          ) : (
            <MobileNavButton
              onClick={() => {
                setEarly("open");
                menu.now();
              }}
              onFocus={() => {
                setEarly((was) => was ?? "focus");
                menu.now();
              }}
            />
          )}

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
              <Suspense fallback={<BellButton />}>
                <NotificationBell />
              </Suspense>
              <CartBadge />
              <Suspense fallback={<AccountButton user={user} />}>
                <UserMenu user={user} />
              </Suspense>
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
