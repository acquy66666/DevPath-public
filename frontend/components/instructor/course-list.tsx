"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ChevronRight, MessageCircleQuestion, Pencil, Plus } from "lucide-react";
import Link from "next/link";
import { useState, type ReactNode } from "react";

import { CourseCover } from "@/components/courses/course-cover";
import { CourseStatusBadge } from "@/components/instructor/course-status-badge";
import { InstructorGreeting } from "@/components/instructor/instructor-greeting";
import { useUnansweredCount } from "@/components/instructor/instructor-nav";
import { OverviewBodySkeleton } from "@/components/instructor/instructor-skeletons";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { greetingName } from "@/lib/account/welcome";
import { listMyCourses, type Course, type CourseStatus } from "@/lib/api/courses";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { useAuth } from "@/lib/auth/auth-provider";
import { formatDate, formatDuration, formatPrice } from "@/lib/format";
import {
  filterCourses,
  greetingLine,
  pendingTasks,
  visibleFilters,
  type Task,
} from "@/lib/instructor/teaching-view";
import { cn } from "@/lib/utils";

/** The most an instructor's list shows at once; past this the list says so. */
const PAGE_SIZE = 100;

/**
 * `/giang-day`: who is teaching, what is waiting for them, and their courses.
 *
 * Every course comes in one request (the Q&A filter already asks for the same
 * list under the same key), so the status chips count and filter on the
 * client: an instructor with more than a hundred courses is not a case this
 * platform has.
 */
export function CourseList() {
  const { accessToken, user } = useAuth();
  const [status, setStatus] = useState<CourseStatus | "all">("all");

  const query = useQuery({
    queryKey: ["my-courses", "all"],
    queryFn: () => listMyCourses(accessToken as string, 1, PAGE_SIZE),
    enabled: accessToken !== null,
  });
  const unanswered = useUnansweredCount();

  if (query.isPending) return <OverviewBodySkeleton />;
  if (query.isError) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{apiErrorMessage(query.error)}</AlertDescription>
      </Alert>
    );
  }

  const courses = query.data.items;
  const tasks = pendingTasks(courses, unanswered.data ?? 0);
  const students = courses.reduce((sum, course) => sum + course.students_count, 0);
  const shown = filterCourses(courses, status);

  return (
    <div className="space-y-8">
      <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_26rem] lg:gap-6">
        <InstructorGreeting
          name={user ? greetingName(user.full_name) : null}
          line={greetingLine(courses.length, students, tasks.length)}
        />
        {courses.length > 0 ? <Tasks tasks={tasks} /> : null}
      </div>

      <Button asChild size="lg" className="w-full sm:hidden">
        <Link href="/giang-day/moi">
          <Plus aria-hidden />
          Tạo khóa học
        </Link>
      </Button>

      {courses.length === 0 ? (
        <NoCourses />
      ) : (
        <section aria-labelledby="my-courses" className="space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <h2 id="my-courses" className="text-h3">
              Khóa học của bạn
            </h2>
            <div
              role="group"
              aria-label="Lọc theo trạng thái"
              className="relative -mx-4 flex gap-1.5 overflow-x-auto px-4 pb-0.5 sm:mx-0 sm:flex-wrap sm:px-0"
            >
              {visibleFilters(courses).map((filter) => (
                <button
                  key={filter.value}
                  type="button"
                  aria-pressed={status === filter.value}
                  onClick={() => setStatus(filter.value)}
                  className={cn(
                    "inline-flex h-8 shrink-0 items-center rounded-full border px-3 text-[0.8125rem] whitespace-nowrap transition-colors duration-fast",
                    status === filter.value
                      ? "border-primary bg-secondary font-semibold text-secondary-foreground"
                      : "border-border-strong bg-card text-muted-foreground hover:bg-accent hover:text-foreground",
                  )}
                >
                  {filter.label} · {filter.count}
                </button>
              ))}
            </div>
          </div>

          <ul className="divide-y overflow-hidden rounded-xl border bg-card">
            {shown.map((course) => (
              <CourseRow key={course.id} course={course} />
            ))}
          </ul>
          {query.data.total > courses.length ? (
            <p className="text-body-sm text-muted-foreground">
              Đang hiện {courses.length} trên {query.data.total} khóa học.
            </p>
          ) : null}
        </section>
      )}
    </div>
  );
}

function courseMeta(course: Course): string {
  const parts = [
    formatPrice(course.price),
    course.students_count > 0 ? `${course.students_count} học viên` : "chưa có học viên",
  ];
  const duration = formatDuration(course.duration_total_s);
  if (duration && course.duration_total_s >= 60) parts.push(duration);
  parts.push(`cập nhật ${formatDate(course.updated_at)}`);
  return parts.join(" · ");
}

function CourseRow({ course }: { course: Course }) {
  return (
    <li>
      <Link
        href={`/giang-day/${course.id}`}
        className="grid grid-cols-[5rem_minmax(0,1fr)] items-start gap-3 p-3 transition-colors duration-fast hover:bg-muted sm:grid-cols-[8rem_minmax(0,1fr)_auto_1.25rem] sm:items-center sm:gap-5 sm:px-5 sm:py-3.5"
      >
        <CourseCover
          thumbnailUrl={course.thumbnail_url}
          colorKey={course.id}
          size="sm"
          className="aspect-video w-full rounded-md"
        />
        <span className="flex min-w-0 flex-col gap-1.5 sm:gap-1">
          <span className="text-title text-pretty sm:truncate">{course.title}</span>
          <span className="sm:hidden">
            <CourseStatusBadge status={course.status} />
          </span>
          <span className="text-caption text-muted-foreground">{courseMeta(course)}</span>
        </span>
        <span className="hidden sm:block">
          <CourseStatusBadge status={course.status} />
        </span>
        <ChevronRight className="hidden size-5 text-muted-foreground sm:block" aria-hidden />
      </Link>
    </li>
  );
}

const TASK_STYLE: Record<Task["kind"], { icon: ReactNode; className: string }> = {
  questions: { icon: <MessageCircleQuestion aria-hidden />, className: "bg-info-soft text-info-text" },
  rejected: { icon: <AlertTriangle aria-hidden />, className: "bg-destructive-soft text-destructive-text" },
  draft: { icon: <Pencil aria-hidden />, className: "bg-muted text-muted-foreground" },
};

function taskText(task: Task): { text: string; action: string } {
  if (task.kind === "questions") {
    return { text: `${task.count} câu hỏi chưa có câu trả lời của bạn`, action: "Trả lời" };
  }
  if (task.kind === "rejected") return { text: `“${task.title}” bị từ chối`, action: "Xem lý do" };
  return { text: `“${task.title}” còn là bản nháp`, action: "Soạn tiếp" };
}

/** What is waiting, as links: the whole row goes there, the action word says what for. */
function Tasks({ tasks }: { tasks: Task[] }) {
  return (
    <section aria-labelledby="waiting" className="rounded-lg border bg-card p-4 sm:p-5">
      <h2 id="waiting" className="text-title">
        Việc đang chờ
      </h2>
      {tasks.length === 0 ? (
        <p className="mt-2 text-body-sm text-muted-foreground">
          Không có việc nào. Câu hỏi mới của học viên và khóa bị trả lại sẽ hiện ở đây.
        </p>
      ) : (
        <ul className="mt-2 divide-y">
          {tasks.slice(0, 5).map((task) => {
            const style = TASK_STYLE[task.kind];
            const { text, action } = taskText(task);
            return (
              <li key={task.kind === "questions" ? "questions" : task.courseId}>
                <Link href={task.href} className="group flex items-center gap-3 py-2.5">
                  <span
                    className={cn(
                      "flex size-8 shrink-0 items-center justify-center rounded-sm [&_svg]:size-4",
                      style.className,
                    )}
                  >
                    {style.icon}
                  </span>
                  <span className="min-w-0 flex-1 text-body-sm break-words">{text}</span>
                  <span className="text-body-sm font-medium whitespace-nowrap text-link group-hover:underline">
                    {action}
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </section>
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
