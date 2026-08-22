"use client";

import Link from "next/link";
import type { ReactNode } from "react";

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
 * Everything under `/giang-day` is for instructors.
 *
 * This is presentation, not protection: the session lives in an HttpOnly
 * cookie on the backend's origin, which Next's middleware cannot read, and a
 * check that runs in the browser is a check the browser can skip. The
 * authorization that counts is `require_role("instructor")` on every endpoint
 * behind these screens -- this only saves an instructor-less visitor from a
 * page full of failed requests.
 */
export function InstructorGate({ children }: { children: ReactNode }) {
  const { user, status } = useAuth();

  if (status === "loading") {
    return (
      <div className="mx-auto max-w-4xl px-4 py-12">
        <div className="h-64 animate-pulse rounded-xl border bg-muted/40" />
      </div>
    );
  }

  if (user === null) {
    return (
      <Prompt
        title="Đăng nhập để vào khu vực giảng viên"
        description="Trang này quản lý khóa học của riêng bạn."
        action={{ href: "/dang-nhap", label: "Đăng nhập" }}
      />
    );
  }

  if (user.role === "student") {
    return (
      <Prompt
        title="Bạn chưa phải giảng viên"
        description="Nâng cấp tài khoản lên giảng viên để bắt đầu tạo khóa học. Chỉ mất một cú nhấp."
        action={{ href: "/tro-thanh-giang-vien", label: "Trở thành giảng viên" }}
      />
    );
  }

  // Admins included: `require_role("instructor")` on the endpoints is an exact
  // match, so an admin who got in here would meet a 403 at every request. They
  // moderate courses, they do not author them.
  if (user.role !== "instructor") {
    return (
      <Prompt
        title="Khu vực dành cho giảng viên"
        description="Tài khoản quản trị không tạo khóa học. Đăng nhập bằng tài khoản giảng viên để vào đây."
        action={{ href: "/", label: "Về trang chủ" }}
      />
    );
  }

  return <>{children}</>;
}

function Prompt({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action: { href: string; label: string };
}) {
  return (
    <div className="mx-auto max-w-xl px-4 py-12">
      <Card>
        <CardHeader>
          <CardTitle>{title}</CardTitle>
          <CardDescription>{description}</CardDescription>
        </CardHeader>
        <CardContent>
          <Button asChild>
            <Link href={action.href}>{action.label}</Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
