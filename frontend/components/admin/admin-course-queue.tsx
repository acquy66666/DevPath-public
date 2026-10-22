"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { BookCheck, ImageOff } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { ADMIN_KEY } from "@/components/admin/admin-nav";
import { EmptyState, ListSkeleton, SearchBox } from "@/components/admin/admin-shared";
import { CourseStatusBadge } from "@/components/instructor/course-status-badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { NativeSelect } from "@/components/ui/native-select";
import { Pager } from "@/components/ui/pager";
import { listAdminCourses, type AdminCourse, type AdminCourseFilter } from "@/lib/api/admin";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { useAuth } from "@/lib/auth/auth-provider";
import { formatDuration, formatPrice, formatRelativeTime } from "@/lib/format";

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

  const courses = useQuery({
    queryKey: [...ADMIN_KEY, "courses", status, q, page],
    queryFn: () => listAdminCourses(accessToken as string, { status, q, page }),
    enabled: accessToken !== null,
    placeholderData: keepPreviousData,
  });

  return (
    <section className="space-y-4" aria-labelledby="admin-courses-title">
      <h2 id="admin-courses-title" className="sr-only">
        Duyệt khóa học
      </h2>

      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2">
          <label htmlFor="admin-course-status" className="text-sm text-muted-foreground">
            Trạng thái
          </label>
          <NativeSelect
            id="admin-course-status"
            className="h-9 w-auto"
            value={status}
            onChange={(event) => {
              setStatus(event.target.value as AdminCourseFilter);
              setPage(1);
            }}
          >
            {FILTERS.map((filter) => (
              <option key={filter.value} value={filter.value}>
                {filter.label}
              </option>
            ))}
          </NativeSelect>
        </div>
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
          icon={BookCheck}
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
  const when =
    course.status === "pending_review"
      ? `gửi duyệt ${formatRelativeTime(course.updated_at)}`
      : `cập nhật ${formatRelativeTime(course.updated_at)}`;

  return (
    <Link
      href={`/quan-tri/khoa-hoc/${course.id}`}
      className="flex gap-4 rounded-lg border p-3 transition-colors hover:bg-muted/50 focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
    >
      <div className="hidden aspect-video w-32 shrink-0 overflow-hidden rounded-md bg-muted sm:block">
        {course.thumbnail_url ? (
          // eslint-disable-next-line @next/next/no-img-element -- R2/MinIO URLs, not optimisable here
          <img src={course.thumbnail_url} alt="" className="size-full object-cover" />
        ) : (
          <div className="flex size-full items-center justify-center text-muted-foreground">
            <ImageOff className="size-5" aria-hidden />
          </div>
        )}
      </div>
      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex items-start justify-between gap-3">
          <p className="min-w-0 font-medium break-words">{course.title}</p>
          <CourseStatusBadge status={course.status} />
        </div>
        <p className="truncate text-sm text-muted-foreground">
          {course.instructor.full_name} · {course.instructor.email}
        </p>
        <p className="text-xs text-muted-foreground">
          {course.category.name} · {course.lessons_count} bài học
          {duration ? ` · ${duration}` : ""} · {formatPrice(course.price)} · {when}
        </p>
      </div>
    </Link>
  );
}
