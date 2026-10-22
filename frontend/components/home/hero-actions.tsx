"use client";

import Link from "next/link";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth/auth-provider";

/**
 * The hero's two buttons. The second one depends on who is reading: a visitor
 * is offered an account, someone signed in is offered their own courses --
 * "Tạo tài khoản miễn phí" to a learner who has one was a dead end.
 *
 * The visitor's version is what the server renders and what shows while the
 * session is being restored, so a signed-out page never flickers. Both
 * buttons are the same height, so the swap does not move anything.
 */
export function HeroActions() {
  const { status } = useAuth();
  const signedIn = status === "authenticated";

  return (
    <div className="flex flex-wrap gap-3">
      <Button size="lg" asChild>
        <Link href="/khoa-hoc">Khám phá khóa học</Link>
      </Button>
      <Button size="lg" variant="outline" asChild>
        {signedIn ? (
          <Link href="/khoa-hoc-cua-toi">Khóa học của tôi</Link>
        ) : (
          <Link href="/dang-ky">Tạo tài khoản miễn phí</Link>
        )}
      </Button>
    </div>
  );
}
