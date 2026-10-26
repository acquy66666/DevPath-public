"use client";

import { useQuery } from "@tanstack/react-query";
import { Award, Check } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { CourseCard, CourseListSkeleton } from "@/components/courses/course-card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { listMyEnrollments } from "@/lib/api/enrollments";
import { useAuth } from "@/lib/auth/auth-provider";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";

/**
 * Guarded here rather than in middleware, for the reason the profile page
 * gives: the session lives in a cookie on the backend's origin, which Next's
 * middleware cannot read. The real protection is the API — `/enrollments/me`
 * answers 401 without a token, whatever this component decides to draw.
 */
export function MyCourses() {
  const { accessToken, status } = useAuth();
  const [page, setPage] = useState(1);

  const query = useQuery({
    queryKey: ["my-enrollments", page],
    queryFn: () => listMyEnrollments(accessToken as string, page),
    enabled: status === "authenticated" && accessToken !== null,
  });

  if (status === "loading") {
    return (
      <CourseListSkeleton label="Đang tải khóa học của bạn…" />
    );
  }

  if (status === "anonymous") {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Đăng nhập để xem khóa học của bạn</CardTitle>
          <CardDescription>
            Danh sách này chỉ hiển thị khóa học của riêng bạn.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button asChild>
            <Link href="/dang-nhap?next=/khoa-hoc-cua-toi">Đăng nhập</Link>
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (query.isError) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{apiErrorMessage(query.error)}</AlertDescription>
      </Alert>
    );
  }

  if (!query.data) {
    return (
      <CourseListSkeleton label="Đang tải khóa học của bạn…" />
    );
  }

  if (query.data.items.length === 0) {
    return (
      <EmptyState
        mood="empty-courses"
        title="Chưa có khóa học nào"
        description="Khóa học miễn phí đăng ký được ngay, không cần thanh toán."
        action={
          <Button asChild>
            <Link href="/khoa-hoc">Tìm khóa học</Link>
          </Button>
        }
      />
    );
  }

  const pageCount = Math.max(
    1,
    Math.ceil(query.data.total / query.data.page_size),
  );

  // "· 2 đã hoàn thành" only when every course is on this page: counting one
  // page of several would say less than the truth.
  const finished = query.data.items.filter((item) => item.completed_at).length;
  const summary =
    pageCount === 1 && finished > 0
      ? `${query.data.total} khóa học · ${finished} đã hoàn thành`
      : `${query.data.total} khóa học`;

  return (
    <div className="space-y-6">
      <p className="text-muted-foreground">{summary}</p>

      {/* Two across at most: from `lg` the achievements take the right-hand column. */}
      <ul className="grid gap-x-5 gap-y-6 sm:grid-cols-2">
        {query.data.items.map((item) => (
          <li key={item.course.id} className="flex h-full flex-col gap-2.5">
            {/* The card takes what the footer leaves: every footer has the same
                two lines (status, then buttons), so cards side by side line up. */}
            <div className="flex flex-1 flex-col *:flex-1">
              <CourseCard course={item.course} />
            </div>
            <div className="flex flex-col gap-2 px-1">
              {item.completed_at ? (
                <p className="flex items-center gap-1.5 text-caption text-success-text">
                  <Check className="size-3.5 shrink-0" strokeWidth={2.5} aria-hidden />
                  Hoàn thành {formatDate(item.completed_at)}
                </p>
              ) : (
                <p className="text-caption text-muted-foreground">
                  Đăng ký {formatDate(item.enrolled_at)}
                </p>
              )}
              <div className="flex shrink-0 gap-2">
                {item.certificate_code ? (
                  // A certificate is a reward: the one button here in the reward tint.
                  <Link
                    href={`/cert/${item.certificate_code}`}
                    className={cn(
                      buttonVariants({ size: "sm", variant: "ghost" }),
                      "bg-reward-soft text-reward-foreground hover:bg-reward/20 hover:text-reward-foreground [&_svg]:text-reward-mark",
                    )}
                  >
                    <Award aria-hidden />
                    Chứng chỉ
                  </Link>
                ) : null}
                <Button size="sm" variant="outline" asChild>
                  <Link href={`/hoc/${item.course.slug}`}>
                    {item.completed_at ? "Xem lại" : "Tiếp tục học"}
                  </Link>
                </Button>
              </div>
            </div>
          </li>
        ))}
      </ul>

      {pageCount > 1 ? (
        <div className="flex items-center justify-center gap-3">
          <Button
            variant="outline"
            size="sm"
            disabled={page === 1}
            onClick={() => setPage((current) => current - 1)}
          >
            Trang trước
          </Button>
          <span className="text-sm text-muted-foreground">
            Trang {page} / {pageCount}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= pageCount}
            onClick={() => setPage((current) => current + 1)}
          >
            Trang sau
          </Button>
        </div>
      ) : null}
    </div>
  );
}
