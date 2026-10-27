"use client";

import Link from "next/link";

import { Mascot } from "@/components/mascot/mascot";
import { AccountCard } from "@/components/profile/account-card";
import { PasswordForm } from "@/components/profile/password-form";
import { ProfileForm } from "@/components/profile/profile-form";
import { Button } from "@/components/ui/button";
import { Skeleton, SkeletonRegion } from "@/components/ui/skeleton";
import { authHref } from "@/lib/account/welcome";
import { useAuth } from "@/lib/auth/auth-provider";

/**
 * The page is guarded here rather than in middleware: the session lives in the
 * refresh cookie on the backend's origin, which Next's middleware cannot read.
 * The real protection is the API — every endpoint behind this page checks the
 * token itself.
 */
export function ProfileView() {
  const { user, status } = useAuth();

  if (status === "loading") {
    return (
      // The account card and the two settings blocks, at the heights they
      // have once drawn (measured 27/10 at 1440 and 375px, Người mua 08).
      <SkeletonRegion label="Đang tải hồ sơ…" className="flex flex-col gap-8">
        <Skeleton className="h-[348px] rounded-xl md:h-[194px]" />
        <Skeleton className="h-[419px] rounded-lg md:h-[301px]" />
        <Skeleton className="h-[375px] rounded-lg md:h-[301px]" />
      </SkeletonRegion>
    );
  }

  if (user === null) {
    return (
      <div className="mx-auto flex max-w-lg flex-col items-center gap-2 rounded-lg border bg-card px-6 py-8 text-center sm:py-10">
        <Mascot mood="wave" className="size-28 sm:size-32" />
        <h2 className="text-h3 text-balance">Đăng nhập để xem hồ sơ</h2>
        <p className="max-w-[40ch] text-body text-pretty text-muted-foreground">
          Trang này chỉ hiển thị tài khoản của bạn: tên, ảnh đại diện và mật khẩu.
        </p>
        <Button className="mt-2 h-11 sm:h-10" asChild>
          <Link href={authHref("/dang-nhap", "/ho-so")}>Đăng nhập</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-8">
      <AccountCard user={user} />
      <ProfileForm user={user} />
      <PasswordForm user={user} />
    </div>
  );
}
