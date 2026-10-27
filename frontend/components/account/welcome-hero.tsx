"use client";

import Link from "next/link";
import { useEffect, useSyncExternalStore } from "react";

import { Mascot } from "@/components/mascot/mascot";
import { Button } from "@/components/ui/button";
import { SkeletonText } from "@/components/ui/skeleton";
import { authHref, greetingName, welcomeMarker, type WelcomeAction } from "@/lib/account/welcome";
import { useAuth } from "@/lib/auth/auth-provider";
import { readItem, removeItem } from "@/lib/gamification/seen";

/**
 * Whether this tab has just made this account: sign-up leaves the new id in
 * session storage. Read once per page load and taken out of storage at once,
 * so a reload or a second visit is a Naomi already standing there. The answer
 * is kept for the page load (a module-level map) so every render agrees with
 * the first; leaving the page spends it. Same shape as the certificate's.
 */
const fresh = new Map<string, boolean>();
const leaving = new Map<string, number>();

function claim(userId: string): boolean {
  let value = fresh.get(userId);
  if (value === undefined) {
    value = welcomeMarker.shouldWave(readItem("session", welcomeMarker.key), userId);
    if (value) removeItem("session", welcomeMarker.key);
    fresh.set(userId, value);
  }
  return value;
}

const never = () => () => {};

/**
 * The top of the welcome page: Naomi says hello -- waving once, for the
 * account just made in this tab -- and one button goes where the visitor was
 * headed before signing up. A visitor who is not signed in is offered an
 * account instead.
 */
export function WelcomeHero({ action, next }: { action: WelcomeAction; next: string }) {
  const { user, status } = useAuth();
  const userId = user?.id ?? null;
  const wave = useSyncExternalStore(never, () => (userId ? claim(userId) : false), () => false);
  useEffect(() => {
    if (!userId) return;
    window.clearTimeout(leaving.get(userId));
    return () => void leaving.set(userId, window.setTimeout(() => fresh.set(userId, false), 0));
  }, [userId]);

  const name = user ? greetingName(user.full_name) : null;
  const secondary =
    action.href === "/khoa-hoc"
      ? { href: "/", label: "Về trang chủ" }
      : { href: "/khoa-hoc", label: "Xem mọi khóa học" };

  return (
    <section className="grid items-center justify-items-center gap-4 rounded-xl bg-secondary px-5 py-7 text-center md:grid-cols-[13.75rem_minmax(0,1fr)] md:justify-items-start md:gap-10 md:px-12 md:py-10 md:text-left">
      <Mascot mood="wave" event={wave && userId ? userId : null} className="size-38 md:size-55" />
      <div className="flex min-w-0 flex-col items-center gap-4 md:items-start">
        <p className="text-eyebrow text-link uppercase">
          {user ? "Tài khoản đã sẵn sàng" : "Chào mừng tới DevPath"}
        </p>
        {status === "loading" ? (
          <SkeletonText size="h1" className="w-72 max-w-full" />
        ) : (
          <h1 className="text-h1 text-balance md:text-display">
            Chào {name ?? "bạn"}, mình là Naomi!
          </h1>
        )}
        <p className="max-w-[34em] text-body-lg text-foreground/80">
          Mình là tắc kè bắt bug của DevPath. Bài nào bạn nộp, mình xem cùng bạn: đúng thì ăn mừng, sai
          thì chỉ chỗ cần sửa.
        </p>
        <div className="flex w-full flex-col gap-2.5 pt-1 sm:w-auto sm:flex-row sm:flex-wrap sm:gap-3">
          {status === "anonymous" ? (
            <Button size="lg" asChild>
              <Link href={authHref("/dang-ky", next)}>Tạo tài khoản miễn phí</Link>
            </Button>
          ) : (
            <Button size="lg" className="h-auto min-h-11 py-2.5 whitespace-normal" asChild>
              <Link href={action.href}>{action.label}</Link>
            </Button>
          )}
          <Button size="lg" variant="outline" asChild>
            <Link href={secondary.href}>{secondary.label}</Link>
          </Button>
        </div>
      </div>
    </section>
  );
}
