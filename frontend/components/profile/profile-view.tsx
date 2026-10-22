"use client";

import Link from "next/link";

import { AvatarForm } from "@/components/profile/avatar-form";
import { PasswordForm } from "@/components/profile/password-form";
import { ProfileForm } from "@/components/profile/profile-form";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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
      <div className="space-y-6">
        <div className="h-64 animate-pulse rounded-lg border bg-muted/40" />
        <div className="h-56 animate-pulse rounded-lg border bg-muted/40" />
      </div>
    );
  }

  if (user === null) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Đăng nhập để xem hồ sơ</CardTitle>
          <CardDescription>Trang này chỉ hiển thị tài khoản của bạn.</CardDescription>
        </CardHeader>
        <CardContent>
          <Button asChild>
            <Link href="/dang-nhap">Đăng nhập</Link>
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <AvatarForm user={user} />
      <ProfileForm user={user} />
      <PasswordForm user={user} />
    </div>
  );
}
