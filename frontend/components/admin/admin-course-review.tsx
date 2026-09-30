"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  CheckCircle2,
  Code2,
  ExternalLink,
  FileText,
  ListChecks,
  Loader2,
  Video,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { ADMIN_KEY } from "@/components/admin/admin-nav";
import { ListSkeleton, PersonLine } from "@/components/admin/admin-shared";
import { CourseStatusBadge } from "@/components/instructor/course-status-badge";
import { VideoPlayer } from "@/components/learn/video-player";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Markdown } from "@/components/ui/markdown";
import { Textarea } from "@/components/ui/textarea";
import {
  approveCourse,
  getAdminCourse,
  rejectCourse,
  takeDownCourse,
  type AdminCourse,
} from "@/lib/api/admin";
import { getCurriculum, getLesson, type LessonType } from "@/lib/api/curriculum";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { useAuth } from "@/lib/auth/auth-provider";
import { LEVEL_LABELS } from "@/lib/courses/labels";
import { formatDate, formatDuration, formatPrice } from "@/lib/format";
import { cn } from "@/lib/utils";

const TYPE_LABELS: Record<LessonType, string> = {
  video: "Video",
  article: "Bài đọc",
  quiz: "Trắc nghiệm",
  code_exercise: "Bài tập code",
};

const TYPE_ICONS: Record<LessonType, LucideIcon> = {
  video: Video,
  article: FileText,
  quiz: ListChecks,
  code_exercise: Code2,
};

const REASON_MAX_LENGTH = 1000;

/**
 * One course, read the way a reviewer needs to: what it promises, what is
 * actually inside, and the decision.
 *
 * The admin reads the course and its lessons through the ordinary endpoints --
 * `may_manage` already opens a course in any status to an admin -- so what is
 * previewed here is exactly what a student would be sold.
 */
export function AdminCourseReview({ courseId }: { courseId: string }) {
  const { accessToken } = useAuth();

  const course = useQuery({
    queryKey: [...ADMIN_KEY, "course", courseId],
    queryFn: () => getAdminCourse(accessToken as string, courseId),
    enabled: accessToken !== null,
  });

  return (
    <div className="space-y-6">
      <Link
        href="/quan-tri/khoa-hoc"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" aria-hidden />
        Hàng đợi duyệt
      </Link>

      {course.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(course.error)}</AlertDescription>
        </Alert>
      ) : null}

      {course.isPending ? <ListSkeleton rows={2} height="h-40" /> : null}

      {course.data ? (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_18rem]">
          <div className="lg:order-2">
            <DecisionPanel course={course.data} />
          </div>
          <div className="min-w-0 space-y-6 lg:order-1">
            <CourseHeader course={course.data} />
            <section className="space-y-2" aria-labelledby="review-description">
              <h2 id="review-description" className="font-semibold">
                Mô tả
              </h2>
              {course.data.description ? (
                <Markdown className="text-sm">{course.data.description}</Markdown>
              ) : (
                <p className="text-sm text-muted-foreground italic">
                  Giảng viên chưa viết mô tả cho khóa học này.
                </p>
              )}
            </section>
            <CurriculumPreview courseId={courseId} />
          </div>
        </div>
      ) : null}
    </div>
  );
}

function CourseHeader({ course }: { course: AdminCourse }) {
  const duration = formatDuration(course.duration_total_s);
  return (
    <div className="space-y-3">
      {course.thumbnail_url ? (
        // eslint-disable-next-line @next/next/no-img-element -- R2/MinIO URLs, not optimisable here
        <img
          src={course.thumbnail_url}
          alt=""
          className="aspect-video w-full max-w-md rounded-xl border object-cover"
        />
      ) : null}
      <div className="flex flex-wrap items-center gap-2">
        <CourseStatusBadge status={course.status} />
        <Badge variant="outline">{course.category.name}</Badge>
        <Badge variant="outline">{LEVEL_LABELS[course.level]}</Badge>
      </div>
      <h2 className="text-xl font-semibold tracking-tight break-words">{course.title}</h2>
      {course.subtitle ? (
        <p className="text-muted-foreground break-words">{course.subtitle}</p>
      ) : null}
      <div className="text-sm">
        <PersonLine person={course.instructor} label="Giảng viên:" />
      </div>
      <p className="text-sm text-muted-foreground">
        {formatPrice(course.price)} · {course.lessons_count} bài học
        {duration ? ` · ${duration} video` : ""} · {course.students_count} học viên · tạo{" "}
        {formatDate(course.created_at)}
        {course.published_at ? ` · lên sàn lần đầu ${formatDate(course.published_at)}` : ""}
      </p>
    </div>
  );
}

// --- The decision ----------------------------------------------------------

function DecisionPanel({ course }: { course: AdminCourse }) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const [writing, setWriting] = useState<"reject" | "take-down" | null>(null);
  const [reason, setReason] = useState("");
  const [done, setDone] = useState<string | null>(null);

  function adopt(updated: AdminCourse, message: string) {
    queryClient.setQueryData([...ADMIN_KEY, "course", course.id], updated);
    queryClient.invalidateQueries({ queryKey: ADMIN_KEY });
    setWriting(null);
    setReason("");
    setDone(message);
  }

  const approve = useMutation({
    mutationFn: () => approveCourse(accessToken as string, course.id),
    onSuccess: (updated) =>
      adopt(
        updated,
        "Đã duyệt. Khóa học đang hiển thị công khai, giảng viên đã nhận được thông báo. Trợ giảng AI và gợi ý khóa học sẽ nạp nội dung trong vài phút.",
      ),
  });
  const reject = useMutation({
    mutationFn: (text: string) => rejectCourse(accessToken as string, course.id, text),
    onSuccess: (updated) =>
      adopt(updated, "Đã từ chối. Giảng viên nhận được lý do và có thể sửa rồi gửi lại."),
  });
  const takeDown = useMutation({
    mutationFn: (text: string) => takeDownCourse(accessToken as string, course.id, text),
    onSuccess: (updated) =>
      adopt(
        updated,
        "Đã gỡ khóa học khỏi trang công khai. Học viên đã ghi danh giữ nguyên lượt ghi danh; giảng viên nhận được lý do.",
      ),
  });

  const busy = approve.isPending || reject.isPending || takeDown.isPending;
  const error = approve.error ?? reject.error ?? takeDown.error;
  const trimmed = reason.trim();

  return (
    <Card className="lg:sticky lg:top-20">
      <CardHeader>
        <CardTitle>Quyết định</CardTitle>
        <CardDescription>
          {course.status === "pending_review"
            ? "Khóa học chỉ hiện với học viên sau khi được duyệt."
            : course.status === "published"
              ? "Khóa học đang bán. Gỡ khỏi sàn nếu nó vi phạm quy định."
              : course.status === "rejected"
                ? "Khóa học đã bị từ chối, đang chờ giảng viên sửa và gửi lại."
                : "Khóa học là bản nháp, giảng viên chưa gửi duyệt."}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {done ? (
          <Alert>
            <CheckCircle2 aria-hidden />
            <AlertDescription>{done}</AlertDescription>
          </Alert>
        ) : null}
        {error ? (
          <Alert variant="destructive">
            <AlertDescription>{apiErrorMessage(error)}</AlertDescription>
          </Alert>
        ) : null}
        {course.status === "rejected" && course.rejection_reason ? (
          <Alert variant="destructive">
            <AlertTitle>Lý do đã gửi giảng viên</AlertTitle>
            <AlertDescription className="whitespace-pre-line">
              {course.rejection_reason}
            </AlertDescription>
          </Alert>
        ) : null}

        {course.status === "pending_review" && writing === null ? (
          <div className="grid gap-2">
            <Button onClick={() => approve.mutate()} disabled={busy}>
              {approve.isPending ? <Loader2 className="animate-spin" aria-hidden /> : null}
              Duyệt và xuất bản
            </Button>
            <Button variant="outline" onClick={() => setWriting("reject")} disabled={busy}>
              Từ chối…
            </Button>
          </div>
        ) : null}

        {course.status === "published" && writing === null ? (
          <div className="grid gap-2">
            <Button asChild variant="outline">
              <Link href={`/khoa-hoc/${course.slug}`} target="_blank">
                <ExternalLink aria-hidden />
                Xem trang công khai
              </Link>
            </Button>
            <Button variant="destructive" onClick={() => setWriting("take-down")} disabled={busy}>
              Gỡ khỏi sàn…
            </Button>
          </div>
        ) : null}

        {writing !== null ? (
          <form
            className="space-y-2"
            onSubmit={(event) => {
              event.preventDefault();
              if (!trimmed) return;
              if (writing === "reject") reject.mutate(trimmed);
              else takeDown.mutate(trimmed);
            }}
          >
            <label htmlFor="decision-reason" className="text-sm font-medium">
              {writing === "reject" ? "Lý do từ chối" : "Lý do gỡ khỏi sàn"}
            </label>
            <Textarea
              id="decision-reason"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              maxLength={REASON_MAX_LENGTH}
              rows={4}
              placeholder={
                writing === "reject"
                  ? "Ví dụ: Video bài 3 không có tiếng; mô tả chưa nói học xong làm được gì."
                  : "Ví dụ: Nội dung sao chép từ một khóa học khác."
              }
              autoFocus
            />
            <p className="text-xs text-muted-foreground">
              Giảng viên đọc nguyên văn lý do này trong thông báo và trang quản lý khóa học.
            </p>
            <div className="flex flex-wrap gap-2">
              <Button
                type="submit"
                variant="destructive"
                disabled={busy || trimmed.length === 0}
              >
                {busy ? <Loader2 className="animate-spin" aria-hidden /> : null}
                {writing === "reject" ? "Từ chối khóa học" : "Gỡ khỏi sàn"}
              </Button>
              <Button
                type="button"
                variant="ghost"
                onClick={() => {
                  setWriting(null);
                  setReason("");
                }}
                disabled={busy}
              >
                Hủy
              </Button>
            </div>
          </form>
        ) : null}
      </CardContent>
    </Card>
  );
}

// --- What is inside --------------------------------------------------------

function CurriculumPreview({ courseId }: { courseId: string }) {
  const { accessToken } = useAuth();
  const [open, setOpen] = useState<string | null>(null);

  const curriculum = useQuery({
    queryKey: [...ADMIN_KEY, "curriculum", courseId],
    queryFn: () => getCurriculum(courseId, accessToken),
    enabled: accessToken !== null,
  });

  return (
    <section className="space-y-2" aria-labelledby="review-curriculum">
      <h2 id="review-curriculum" className="font-semibold">
        Nội dung khóa học
      </h2>
      {curriculum.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(curriculum.error)}</AlertDescription>
        </Alert>
      ) : null}
      {curriculum.isPending ? <ListSkeleton rows={2} height="h-12" /> : null}
      {curriculum.data && curriculum.data.sections.length === 0 ? (
        <p className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
          Khóa học chưa có chương nào — đây thường là lý do nên từ chối.
        </p>
      ) : null}
      {curriculum.data && curriculum.data.sections.length > 0 ? (
        <div className="overflow-hidden rounded-lg border">
          {curriculum.data.sections.map((section) => (
            <div key={section.id} className="border-b last:border-b-0">
              <p className="bg-muted/40 px-4 py-2 text-sm font-medium break-words">
                {section.title}
              </p>
              {section.lessons.length === 0 ? (
                <p className="border-t px-4 py-2 text-sm text-muted-foreground">
                  Chương này chưa có bài học.
                </p>
              ) : (
                <ul>
                  {section.lessons.map((lesson) => {
                    const Icon = TYPE_ICONS[lesson.type];
                    const expanded = open === lesson.id;
                    return (
                      <li key={lesson.id} className="border-t">
                        <button
                          type="button"
                          aria-expanded={expanded}
                          onClick={() => setOpen(expanded ? null : lesson.id)}
                          className={cn(
                            "flex w-full items-center gap-3 px-4 py-2 text-left text-sm hover:bg-muted/50 focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none",
                            expanded && "bg-muted/50",
                          )}
                        >
                          <Icon className="size-4 shrink-0 text-muted-foreground" aria-hidden />
                          <span className="min-w-0 flex-1 break-words">{lesson.title}</span>
                          {lesson.is_preview ? <Badge variant="outline">Học thử</Badge> : null}
                          <span className="shrink-0 text-xs text-muted-foreground">
                            {TYPE_LABELS[lesson.type]}
                          </span>
                        </button>
                        {expanded ? <LessonPreview lessonId={lesson.id} /> : null}
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function LessonPreview({ lessonId }: { lessonId: string }) {
  const { accessToken } = useAuth();
  const lesson = useQuery({
    queryKey: [...ADMIN_KEY, "lesson", lessonId],
    queryFn: () => getLesson(lessonId, accessToken),
    enabled: accessToken !== null,
  });

  return (
    <div className="space-y-3 border-t bg-background px-4 py-4">
      {lesson.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(lesson.error)}</AlertDescription>
        </Alert>
      ) : null}
      {lesson.isPending ? <div className="h-24 animate-pulse rounded-lg bg-muted/40" /> : null}
      {lesson.data ? (
        lesson.data.type === "video" ? (
          lesson.data.video?.hls_url ? (
            <VideoPlayer
              src={lesson.data.video.hls_url}
              startAt={0}
              onProgress={() => {}}
              onEnded={() => {}}
            />
          ) : (
            <p className="text-sm text-muted-foreground">
              {lesson.data.video?.status === "processing"
                ? "Video đang được xử lý."
                : lesson.data.video?.status === "failed"
                  ? "Video chuyển mã thất bại — học viên sẽ không xem được bài này."
                  : "Bài học này chưa có video."}
            </p>
          )
        ) : lesson.data.type === "article" ? (
          lesson.data.article_content ? (
            <Markdown className="text-sm">{lesson.data.article_content}</Markdown>
          ) : (
            <p className="text-sm text-muted-foreground">Bài đọc này chưa có nội dung.</p>
          )
        ) : (
          <p className="text-sm text-muted-foreground">
            {lesson.data.type === "quiz" ? "Bài trắc nghiệm" : "Bài tập code"} — nội dung
            câu hỏi và test case không xem trước ở đây.
          </p>
        )
      ) : null}
    </div>
  );
}
