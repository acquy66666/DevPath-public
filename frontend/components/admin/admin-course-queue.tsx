"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { ADMIN_KEY, useAdminSummary } from "@/components/admin/admin-nav";
import { AdminTitle, EmptyState, ListSkeleton, SearchBox } from "@/components/admin/admin-shared";
import { FilterChips } from "@/components/admin/filter-chips";
import { CourseCover } from "@/components/courses/course-cover";
import { CourseStatusBadge } from "@/components/instructor/course-status-badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { buttonVariants } from "@/components/ui/button";
import { Pager } from "@/components/ui/pager";
import { listAdminCourses, type AdminCourse, type AdminCourseFilter } from "@/lib/api/admin";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { useAuth } from "@/lib/auth/auth-provider";
import { LONG_WAIT_DAYS, waitedDays, waitLabel } from "@/lib/admin/admin-view";
import { formatDate, formatDuration, formatPrice, formatRelativeTime } from "@/lib/format";
import { cn } from "@/lib/utils";

const FILTERS: { value: AdminCourseFilter; label: string }[] = [
  { value: "pending_review", label: "Chờ duyệt" },
  { value: "published", label: "Đang bán" },
  { value: "rejected", label: "Bị từ chối" },
  { value: "draft", label: "Bản nháp" },
  { value: "all", label: "Tất cả" },
];

/**
 * The review queue: courses instructors have sent, longest waiting first.
 *
 * Opens on "Chờ duyệt" because that is the admin's work; the other statuses
 * are there to find a course already on sale (to take it down) or one that was
 * sent back.
 */
export function AdminCourseQueue() {
  const { accessToken } = useAuth();
  const [status, setStatus] = useState<AdminCourseFilter>("pending_review");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);

  const summary = useAdminSummary();
  const courses = useQuery({
    queryKey: [...ADMIN_KEY, "courses", status, q, page],
    queryFn: () => listAdminCourses(accessToken as string, { status, q, page }),
    enabled: accessToken !== null,
    placeholderData: keepPreviousData,
  });

  return (
    <section className="space-y-5" aria-labelledby="admin-courses-title">
      <AdminTitle
        id="admin-courses-title"
        title="Duyệt khóa học"
        description="Khóa học chỉ hiện với học viên sau khi được duyệt. Chờ lâu nhất đứng đầu."
      />

      <div className="flex flex-wrap items-center gap-3">
        <FilterChips
          label="Lọc theo trạng thái"
          value={status}
          onChange={(value) => {
            setStatus(value);
            setPage(1);
          }}
          options={FILTERS.map((filter) => ({
            ...filter,
            // Only the queue's size is known without asking for every status.
            count: filter.value === "pending_review" ? summary.data?.pending_courses : undefined,
          }))}
        />
        <SearchBox
          id="admin-course-search"
          placeholder="Tên khóa học, tên hoặc email giảng viên"
          initial={q}
          onSearch={(value) => {
            setQ(value);
            setPage(1);
          }}
        />
      </div>

      {courses.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(courses.error)}</AlertDescription>
        </Alert>
      ) : null}

      {courses.isPending ? <ListSkeleton /> : null}

      {courses.data && courses.data.total === 0 ? (
        <EmptyState
          mood={q ? "empty-search" : "empty-courses"}
          title={
            q
              ? "Không có khóa học nào khớp"
              : status === "pending_review"
                ? "Không còn khóa học nào chờ duyệt"
                : "Chưa có khóa học nào ở trạng thái này"
          }
          hint={
            status === "pending_review"
              ? "Khi giảng viên bấm “Gửi duyệt”, khóa học sẽ xếp hàng ở đây, chờ lâu nhất đứng đầu."
              : "Đổi bộ lọc trạng thái hoặc từ khóa tìm kiếm để xem khóa học khác."
          }
        />
      ) : null}

      {courses.data && courses.data.items.length > 0 ? (
        <ul
          className={courses.isPlaceholderData ? "space-y-3 opacity-60" : "space-y-3"}
          aria-busy={courses.isFetching}
        >
          {courses.data.items.map((course) => (
            <li key={course.id}>
              <CourseRow course={course} />
            </li>
          ))}
        </ul>
      ) : null}

      {courses.data ? (
        <Pager
          page={courses.data.page}
          pageSize={courses.data.page_size}
          total={courses.data.total}
          onPage={setPage}
        />
      ) : null}
    </section>
  );
}

function CourseRow({ course }: { course: AdminCourse }) {
  const duration = formatDuration(course.duration_total_s);
  const pending = course.status === "pending_review";
  const days = waitedDays(course.updated_at, new Date());

  return (
    <Link
      href={`/quan-tri/khoa-hoc/${course.id}`}
      className="flex items-center gap-4 rounded-lg border bg-card p-3 transition-colors duration-fast hover:border-primary sm:p-4"
    >
      <div className="hidden w-32 shrink-0 overflow-hidden rounded-md sm:block">
        <CourseCover thumbnailUrl={course.thumbnail_url} colorKey={course.id} size="xs" />
      </div>
      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <p className="min-w-0 text-title break-words">{course.title}</p>
          <CourseStatusBadge status={course.status} />
        </div>
        <p className="truncate text-body-sm text-muted-foreground">
          {course.instructor.full_name} · {course.instructor.email}
        </p>
        <p className="text-caption text-muted-foreground">
          {pending ? (
            <>
              Gửi duyệt {formatDate(course.updated_at)} ·{" "}
              <span className={cn(days >= LONG_WAIT_DAYS && "font-semibold text-warning-text")}>
                {waitLabel(days)}
              </span>
            </>
          ) : (
            `Cập nhật ${formatRelativeTime(course.updated_at)}`
          )}{" "}
          · {course.category.name} · {course.lessons_count} bài học
          {duration ? ` · ${duration}` : ""} · {formatPrice(course.price)}
        </p>
      </div>
      {pending ? (
        <span className={cn(buttonVariants({ size: "sm" }), "hidden shrink-0 md:inline-flex")} aria-hidden>
          Xem và duyệt
        </span>
      ) : null}
    </Link>
  );
}
