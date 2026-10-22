"use client";

import { useMutation } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { ReactNode } from "react";

import { Mascot } from "@/components/mascot/mascot";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton, SkeletonText } from "@/components/ui/skeleton";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { becomeInstructor } from "@/lib/api/users";
import { useAuth } from "@/lib/auth/auth-provider";

/** The card's frame, the same in every state so the column does not jump. */
function Frame({ children }: { children: ReactNode }) {
  return <div className="space-y-4 rounded-lg border bg-card p-6">{children}</div>;
}

/**
 * The action beside "Trở thành giảng viên": what it says depends on who is
 * reading -- a visitor is asked to sign in, a learner gets the button, an
 * instructor is sent to the teaching area, an admin is told why not.
 */
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
    return (
      <div aria-hidden>
        <Frame>
          <div className="flex items-center gap-3">
            <Skeleton className="size-18 shrink-0 rounded-full" />
            <div className="flex-1">
              <SkeletonText size="h3" className="w-2/3" />
              <SkeletonText size="body-sm" className="w-1/3" />
            </div>
          </div>
          <div>
            <SkeletonText />
            <SkeletonText className="w-4/5" />
          </div>
          <Skeleton className="h-11 w-full" />
        </Frame>
      </div>
    );
  }

  if (user === null) {
    return (
      <Frame>
        <h2 className="text-h3">Đăng nhập để tiếp tục</h2>
        <p className="text-body text-foreground/80">
          Nâng cấp tài khoản cần biết bạn là ai. Đăng nhập rồi quay lại trang này nhé.
        </p>
        <div className="flex flex-wrap gap-2">
          <Button size="lg" asChild>
            <Link href="/dang-nhap?next=/tro-thanh-giang-vien">Đăng nhập</Link>
          </Button>
          <Button size="lg" variant="outline" asChild>
            <Link href="/dang-ky?next=/tro-thanh-giang-vien">Tạo tài khoản</Link>
          </Button>
        </div>
      </Frame>
    );
  }

  if (user.role === "instructor") {
    return (
      <Frame>
        <h2 className="text-h3">Bạn đã là giảng viên</h2>
        <p className="text-body text-foreground/80">
          Khóa học, thống kê và hỏi đáp của học viên nằm ở khu giảng dạy.
        </p>
        <Button size="lg" className="w-full" asChild>
          <Link href="/giang-day">Vào khu giảng dạy</Link>
        </Button>
      </Frame>
    );
  }

  if (user.role === "admin") {
    return (
      <Frame>
        <h2 className="text-h3">Tài khoản quản trị</h2>
        <p className="text-body text-foreground/80">
          Quản trị viên đã có mọi quyền của giảng viên, không cần nâng cấp — và nâng cấp sẽ làm mất
          quyền quản trị.
        </p>
      </Frame>
    );
  }

  return (
    <Frame>
      <div className="flex items-center gap-3">
        <Mascot mood="wave" className="size-18 shrink-0" />
        <div className="min-w-0">
          <h2 className="truncate text-h3">Chào {user.full_name}</h2>
          <p className="text-body-sm text-muted-foreground">Tài khoản học viên</p>
        </div>
      </div>

      <p className="text-body text-foreground/80">
        Miễn phí và có hiệu lực ngay. Khóa học đang học, tiến độ và ghi chú của bạn đều giữ nguyên.
      </p>

      {mutation.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(mutation.error)}</AlertDescription>
        </Alert>
      ) : null}

      <Button size="lg" className="w-full" onClick={() => mutation.mutate()} disabled={mutation.isPending}>
        {mutation.isPending ? (
          <>
            <Loader2 className="animate-spin" aria-hidden />
            Đang nâng cấp…
          </>
        ) : (
          "Nâng cấp tài khoản của tôi"
        )}
      </Button>

      <p className="text-caption text-muted-foreground">
        Khóa học bạn tạo ở trạng thái nháp, và phải được quản trị viên duyệt trước khi hiện công khai.
      </p>
    </Frame>
  );
}
