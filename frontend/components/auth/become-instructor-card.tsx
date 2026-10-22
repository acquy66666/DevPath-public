"use client";

import { useMutation } from "@tanstack/react-query";
import { CheckCircle2, Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { becomeInstructor } from "@/lib/api/users";
import { useAuth } from "@/lib/auth/auth-provider";

const WHAT_YOU_GET = [
  "Tạo khóa học: chương, bài giảng, video",
  "Ra bài tập code và bộ test, hệ thống chấm tự động",
  "Sinh quiz từ nội dung bài giảng bằng AI",
  "Xem thống kê học viên và tiến độ hoàn thành",
];

export function BecomeInstructorCard() {
  const router = useRouter();
  const { user, accessToken, status, refreshSession } = useAuth();

  const mutation = useMutation({
    mutationFn: async () => {
      await becomeInstructor(accessToken as string);
      // The role lives in the session the provider holds; re-read it so the
      // header and this page stop calling the user a student.
      await refreshSession();
    },
    onSuccess: () => router.refresh(),
  });

  if (status === "loading") {
    return <Skeleton className="h-64 rounded-lg" />;
  }

  if (user === null) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Đăng nhập để tiếp tục</CardTitle>
          <CardDescription>
            Nâng cấp tài khoản cần biết bạn là ai. Đăng nhập rồi quay lại trang này nhé.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex gap-2">
          <Button asChild>
            <Link href="/dang-nhap">Đăng nhập</Link>
          </Button>
          <Button variant="outline" asChild>
            <Link href="/dang-ky">Tạo tài khoản</Link>
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (user.role === "instructor") {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CheckCircle2 className="size-5 text-emerald-600" aria-hidden />
            Bạn đã là giảng viên
          </CardTitle>
          <CardDescription>
            Trang quản lý khóa học đang được xây dựng — sẽ có ở bước kế tiếp của dự án.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  if (user.role === "admin") {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Tài khoản quản trị</CardTitle>
          <CardDescription>
            Quản trị viên đã có mọi quyền của giảng viên, không cần nâng cấp — và nâng
            cấp sẽ làm mất quyền quản trị.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Trở thành giảng viên</CardTitle>
        <CardDescription>
          Miễn phí và có hiệu lực ngay. Tài khoản học viên của bạn giữ nguyên: khóa học
          đang học, tiến độ, ghi chú đều còn.
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-4">
        <ul className="space-y-2 text-sm">
          {WHAT_YOU_GET.map((item) => (
            <li key={item} className="flex gap-2">
              <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
              {item}
            </li>
          ))}
        </ul>

        <p className="text-sm text-muted-foreground">
          Khóa học bạn tạo sẽ ở trạng thái nháp và phải qua duyệt trước khi hiển thị
          công khai.
        </p>

        {mutation.isError ? (
          <Alert variant="destructive">
            <AlertDescription>{apiErrorMessage(mutation.error)}</AlertDescription>
          </Alert>
        ) : null}

        <Button
          className="w-full"
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending}
        >
          {mutation.isPending ? (
            <>
              <Loader2 className="animate-spin" aria-hidden />
              Đang nâng cấp…
            </>
          ) : (
            "Nâng cấp tài khoản của tôi"
          )}
        </Button>
      </CardContent>
    </Card>
  );
}
