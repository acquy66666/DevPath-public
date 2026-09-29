"use client";

import { useQuery } from "@tanstack/react-query";
import { Award } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { CourseCard } from "@/components/courses/course-card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { listMyEnrollments } from "@/lib/api/enrollments";
import { useAuth } from "@/lib/auth/auth-provider";
import { formatDate } from "@/lib/format";

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
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {[0, 1, 2].map((row) => (
          <div key={row} className="h-72 animate-pulse rounded-xl border bg-muted/40" />
        ))}
      </div>
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
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {[0, 1, 2].map((row) => (
          <div key={row} className="h-72 animate-pulse rounded-xl border bg-muted/40" />
        ))}
      </div>
    );
  }

  if (query.data.items.length === 0) {
    return (
      <div className="rounded-xl border border-dashed p-12 text-center">
        <p className="font-medium">Bạn chưa đăng ký khóa học nào</p>
        <p className="mt-1 text-sm text-muted-foreground">
          Khóa học miễn phí đăng ký được ngay, không cần thanh toán.
        </p>
        <Button className="mt-4" asChild>
          <Link href="/khoa-hoc">Tìm khóa học</Link>
        </Button>
      </div>
    );
  }

  const pageCount = Math.max(
    1,
    Math.ceil(query.data.total / query.data.page_size),
  );

  return (
    <div className="space-y-6">
      <p className="text-muted-foreground">{query.data.total} khóa học</p>

      <ul className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {query.data.items.map((item) => (
          <li key={item.course.id} className="flex h-full flex-col gap-2">
            <CourseCard course={item.course} />
            <div className="flex items-center justify-between gap-3 px-1">
              <p className="text-xs text-muted-foreground">
                {item.completed_at
                  ? `Hoàn thành ${formatDate(item.completed_at)}`
                  : `Đăng ký ${formatDate(item.enrolled_at)}`}
              </p>
              <div className="flex shrink-0 gap-2">
                {item.certificate_code ? (
                  <Button size="sm" variant="secondary" asChild>
                    <Link href={`/cert/${item.certificate_code}`}>
                      <Award aria-hidden />
                      Chứng chỉ
                    </Link>
                  </Button>
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
