"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { AddToCartButton } from "@/components/commerce/add-to-cart-button";
import { WishlistButton } from "@/components/commerce/wishlist-button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { apiErrorMessage } from "@/lib/api/error-messages";
import type { CourseDetail } from "@/lib/api/courses";
import { enrolInCourse, getMyEnrollment } from "@/lib/api/enrollments";
import { useAuth } from "@/lib/auth/auth-provider";

/**
 * The one part of the course page that depends on who is looking.
 *
 * A Client Component on purpose: the page around it is server-rendered the same
 * for everybody, including a crawler, and only this button changes. The access
 * token lives in memory in the browser, so this is also the only place that can
 * ask whether the reader is already enrolled.
 */
export function EnrollButton({ course }: { course: CourseDetail }) {
  const { user, accessToken, status } = useAuth();
  const router = useRouter();
  const queryClient = useQueryClient();
  const free = Number(course.price) === 0;
  const owns = user?.id === course.instructor.id;

  const enrollment = useQuery({
    queryKey: ["enrollment", course.id],
    queryFn: () => getMyEnrollment(accessToken as string, course.id),
    enabled: status === "authenticated" && accessToken !== null && !owns,
  });

  const enrol = useMutation({
    mutationFn: () => enrolInCourse(accessToken as string, course.id),
    onSuccess: (created) => {
      queryClient.setQueryData(["enrollment", course.id], created);
      queryClient.invalidateQueries({ queryKey: ["my-enrollments"] });
      router.push(`/hoc/${course.slug}`);
    },
  });

  if (status === "loading") {
    return <div className="h-9 w-full animate-pulse rounded-lg bg-muted" aria-hidden />;
  }

  if (owns) {
    return (
      <Button className="w-full" variant="outline" asChild>
        <Link href={`/giang-day/${course.id}`}>Quản lý khóa học này</Link>
      </Button>
    );
  }

  if (user === null) {
    return (
      <div className="space-y-2">
        <Button className="w-full" asChild>
          <Link href={`/dang-nhap?next=/khoa-hoc/${course.slug}`}>
            {free ? "Đăng nhập để học miễn phí" : "Đăng nhập"}
          </Link>
        </Button>
        <p className="text-center text-xs text-muted-foreground">
          Chưa có tài khoản?{" "}
          <Link
            href={`/dang-ky?next=/khoa-hoc/${course.slug}`}
            className="underline underline-offset-4"
          >
            Đăng ký
          </Link>
        </p>
      </div>
    );
  }

  if (enrollment.data) {
    return (
      <div className="space-y-2">
        <Button className="w-full" asChild>
          <Link href={`/hoc/${course.slug}`}>Vào học</Link>
        </Button>
        <p className="flex items-center justify-center gap-2 text-xs text-muted-foreground">
          <Check className="size-3.5" aria-hidden />
          Bạn đã đăng ký khóa học này
        </p>
      </div>
    );
  }

  // A paid course is bought through the cart: the checkout behind it is the
  // next task, but the cart is where the intention is collected either way,
  // and a disabled "Mua khóa học" was a dead end for the reader.
  if (!free) {
    return (
      <div className="space-y-2">
        <AddToCartButton courseId={course.id} />
        <WishlistButton courseId={course.id} />
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {enrol.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(enrol.error)}</AlertDescription>
        </Alert>
      ) : null}

      <Button
        className="w-full"
        onClick={() => enrol.mutate()}
        disabled={enrol.isPending || enrollment.isLoading}
      >
        {enrol.isPending ? (
          <>
            <Loader2 className="animate-spin" aria-hidden />
            Đang đăng ký…
          </>
        ) : (
          "Đăng ký học miễn phí"
        )}
      </Button>

      <WishlistButton courseId={course.id} />
    </div>
  );
}
