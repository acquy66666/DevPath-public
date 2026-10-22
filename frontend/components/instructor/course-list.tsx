"use client";

import { useQuery } from "@tanstack/react-query";
import { Award, BarChart3, MessageCircleQuestion, Plus } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { CourseStatusBadge } from "@/components/instructor/course-status-badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { TeachingRowsSkeleton } from "@/components/instructor/instructor-skeletons";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { listMyCourses } from "@/lib/api/courses";
import { useAuth } from "@/lib/auth/auth-provider";
import { formatDate, formatPrice } from "@/lib/format";

export function CourseList() {
  const { accessToken } = useAuth();
  const [page, setPage] = useState(1);

  const query = useQuery({
    queryKey: ["my-courses", page],
    queryFn: () => listMyCourses(accessToken as string, page),
    enabled: accessToken !== null,
  });

  const pageCount = query.data
    ? Math.max(1, Math.ceil(query.data.total / query.data.page_size))
    : 1;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Khóa học của tôi</h1>
          <p className="text-sm text-muted-foreground">
            Nơi bạn soạn nội dung và quyết định khi nào khóa học lên sóng.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button asChild variant="outline">
            <Link href="/giang-day/hoi-dap">
              <MessageCircleQuestion aria-hidden />
              Hỏi đáp
            </Link>
          </Button>
          <Button asChild variant="outline">
            <Link href="/giang-day/thong-ke">
              <BarChart3 aria-hidden />
              Thống kê
            </Link>
          </Button>
          <Button asChild variant="outline">
            <Link href="/giang-day/cap-bac">
              <Award aria-hidden />
              Cấp bậc
            </Link>
          </Button>
          <Button asChild>
            <Link href="/giang-day/moi">
              <Plus aria-hidden />
              Tạo khóa học
            </Link>
          </Button>
        </div>
      </div>

      {query.isPending ? (
        <TeachingRowsSkeleton />
      ) : query.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(query.error)}</AlertDescription>
        </Alert>
      ) : query.data.items.length === 0 ? (
        <NoCourses />
      ) : (
        <ul className="space-y-3">
          {query.data.items.map((course) => (
            <li key={course.id}>
              <Link
                href={`/giang-day/${course.id}`}
                className="block rounded-lg border p-4 transition-colors hover:bg-muted/50 focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="line-clamp-2 font-medium sm:truncate">{course.title}</p>
                    {course.subtitle ? (
                      <p className="truncate text-sm text-muted-foreground">
                        {course.subtitle}
                      </p>
                    ) : null}
                  </div>
                  <CourseStatusBadge status={course.status} />
                </div>
                <p className="mt-2 text-xs text-muted-foreground">
                  {formatPrice(course.price)} · {course.students_count} học viên · cập nhật{" "}
                  {formatDate(course.updated_at)}
                </p>
              </Link>
            </li>
          ))}
        </ul>
      )}

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

function NoCourses() {
  return (
    <EmptyState
      mood="empty-courses"
      size="md"
      title="Chưa có khóa học nào"
      description="Khóa học đầu tiên chỉ cần một cái tên và một danh mục. Nội dung soạn dần sau, và khóa ở dạng nháp cho tới khi bạn gửi duyệt."
      action={
        <Button asChild>
          <Link href="/giang-day/moi">
            <Plus aria-hidden />
            Tạo khóa học đầu tiên
          </Link>
        </Button>
      }
    />
  );
}
