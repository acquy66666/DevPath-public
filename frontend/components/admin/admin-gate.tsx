"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { AdminFrame } from "@/components/admin/admin-frame";
import { AdminBodySkeleton, AdminNavSkeleton } from "@/components/admin/admin-shared";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { SkeletonRegion } from "@/components/ui/skeleton";
import { useAuth } from "@/lib/auth/auth-provider";

/**
 * Everything under `/quan-tri` is for admins.
 *
 * Presentation, like `InstructorGate`: the authorization that counts is
 * `require_role("admin")` on every `/api/v1/admin/*` endpoint. This only spares
 * anyone else a screen full of 403s.
 */
export function AdminGate({ children }: { children: ReactNode }) {
  const { user, status } = useAuth();

  // The admin frame with its menu in bars, then the body every admin screen
  // starts from: the same one quan-tri/loading.tsx shows inside the real frame.
  if (status === "loading") {
    return (
      <SkeletonRegion label="Đang mở khu vực quản trị…">
        <AdminFrame>
          <AdminNavSkeleton />
          <div className="min-w-0 flex-1">
            <AdminBodySkeleton />
          </div>
        </AdminFrame>
      </SkeletonRegion>
    );
  }

  if (user === null) {
    return (
      <Prompt
        title="Đăng nhập để vào khu vực quản trị"
        description="Trang này dành cho quản trị viên của DevPath."
        action={{ href: "/dang-nhap", label: "Đăng nhập" }}
      />
    );
  }

  if (user.role !== "admin") {
    return (
      <Prompt
        title="Khu vực dành cho quản trị viên"
        description="Tài khoản của bạn không có quyền duyệt khóa học hay xử lý báo cáo."
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
