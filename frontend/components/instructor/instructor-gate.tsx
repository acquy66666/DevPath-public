"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, type ReactNode } from "react";

import { InstructorNavSkeleton, instructorSkeletonFor } from "@/components/instructor/instructor-skeletons";
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
  const pathname = usePathname();

  // The skeleton of the screen being opened, not a generic block: the same
  // one its loading.tsx and its first query show.
  if (status === "loading") {
    return (
      <>
        <InstructorNavSkeleton />
        {instructorSkeletonFor(pathname)}
      </>
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

  if (user.role === "student") return <StudentPrompt />;

  // Admins included: `require_role("instructor")` on the endpoints is an exact
  // match, so an admin who got in here would meet a 403 at every request. They
  // moderate courses, they do not author them.
  if (user.role !== "instructor") {
    return (
      <Prompt
        title="Khu vực dành cho giảng viên"
        description="Tài khoản quản trị không tạo khóa học. Việc duyệt khóa học nằm ở khu vực quản trị."
        action={{ href: "/quan-tri", label: "Vào khu vực quản trị" }}
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

/**
 * A student at the door. An admin may have approved them a moment ago in
 * another tab of the world -- the "đã được duyệt" notification links here --
 * while this session still carries the role it was issued with, so read the
 * session again once: if the row says instructor now, the gate opens.
 */
function StudentPrompt() {
  const { refreshSession } = useAuth();
  const asked = useRef(false);

  useEffect(() => {
    if (asked.current) return;
    asked.current = true;
    refreshSession().catch(() => {
      // Signed out meanwhile: the provider has already said so.
    });
  }, [refreshSession]);

  return (
    <Prompt
      title="Bạn chưa phải giảng viên"
      description="Gửi yêu cầu trở thành giảng viên. Quản trị viên duyệt xong là bạn tạo khóa học được."
      action={{ href: "/tro-thanh-giang-vien", label: "Trở thành giảng viên" }}
    />
  );
}
