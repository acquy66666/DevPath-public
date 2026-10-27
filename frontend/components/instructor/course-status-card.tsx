"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Circle, CircleDashed, Clock, Eye, Loader2, Undo2 } from "lucide-react";
import type { ReactNode } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { submitCourse, unpublishCourse, type Course } from "@/lib/api/courses";
import { getCurriculum } from "@/lib/api/curriculum";
import { useAuth } from "@/lib/auth/auth-provider";
import { reviewChecklist } from "@/lib/instructor/teaching-view";
import { cn } from "@/lib/utils";

const STANDING: Record<Course["status"], { icon: ReactNode; title: string; text: string; className: string }> = {
  draft: {
    icon: <CircleDashed aria-hidden />,
    title: "Bản nháp, chỉ mình bạn thấy",
    text: "Gửi duyệt khi đã sẵn sàng: quản trị viên xem rồi đưa khóa học lên trang công khai.",
    className: "text-muted-foreground",
  },
  pending_review: {
    icon: <Clock aria-hidden />,
    title: "Đang chờ quản trị viên duyệt",
    text: "Bạn vẫn sửa được nội dung trong lúc chờ. Có kết quả, bạn nhận được thông báo.",
    className: "text-info-text",
  },
  published: {
    icon: <Eye aria-hidden />,
    title: "Đang hiển thị công khai",
    text: "Khóa học nhận học viên. Sửa nội dung lúc này thì học viên thấy ngay.",
    className: "text-success-text",
  },
  rejected: {
    icon: <Undo2 aria-hidden />,
    title: "Quản trị viên trả lại khóa học",
    text: "Sửa theo góp ý rồi gửi duyệt lại.",
    className: "text-destructive-text",
  },
};

/**
 * Where the course stands and the one move that changes it: send for review,
 * or take it off the public pages. Beside a draft or a rejected course it
 * also lists what admins have sent courses back for -- hints, never a lock on
 * the button, since the backend asks for none of them.
 */
export function CourseStatusCard({ course }: { course: Course }) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const canSubmit = course.status === "draft" || course.status === "rejected";

  const curriculum = useQuery({
    queryKey: ["curriculum", course.id],
    queryFn: () => getCurriculum(course.id, accessToken),
    enabled: accessToken !== null && canSubmit,
  });

  function adopt(updated: Course) {
    queryClient.setQueryData(["course", course.id], updated);
    queryClient.invalidateQueries({ queryKey: ["my-courses"] });
  }

  const submit = useMutation({
    mutationFn: () => submitCourse(accessToken as string, course.id),
    onSuccess: adopt,
  });
  const unpublish = useMutation({
    mutationFn: () => unpublishCourse(accessToken as string, course.id),
    onSuccess: adopt,
  });

  const error = submit.error ?? unpublish.error;
  const standing = STANDING[course.status];
  const checks = canSubmit ? reviewChecklist(course, curriculum.data?.sections) : [];
  const done = checks.filter((check) => check.done).length;

  return (
    <section aria-labelledby="course-standing" className="space-y-3 rounded-lg border bg-card p-5">
      <h2 id="course-standing" className="text-title">
        Trạng thái
      </h2>
      <p className={cn("flex items-center gap-2 text-body-sm font-semibold [&_svg]:size-4 [&_svg]:shrink-0", standing.className)}>
        {standing.icon}
        {standing.title}
      </p>

      {course.status === "rejected" && course.rejection_reason ? (
        <Alert variant="destructive">
          <AlertTitle>Lý do</AlertTitle>
          <AlertDescription className="whitespace-pre-line">{course.rejection_reason}</AlertDescription>
        </Alert>
      ) : null}

      <p className="text-body-sm text-muted-foreground">{standing.text}</p>

      {error ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(error)}</AlertDescription>
        </Alert>
      ) : null}

      {canSubmit ? (
        <Button className="w-full" onClick={() => submit.mutate()} disabled={submit.isPending}>
          {submit.isPending ? (
            <>
              <Loader2 className="animate-spin" aria-hidden />
              Đang gửi…
            </>
          ) : course.status === "rejected" ? (
            "Gửi duyệt lại"
          ) : (
            "Gửi duyệt"
          )}
        </Button>
      ) : null}

      {course.status === "published" ? (
        <Button
          variant="outline"
          className="w-full"
          onClick={() => unpublish.mutate()}
          disabled={unpublish.isPending}
        >
          {unpublish.isPending ? (
            <>
              <Loader2 className="animate-spin" aria-hidden />
              Đang gỡ…
            </>
          ) : (
            "Gỡ khỏi trang công khai"
          )}
        </Button>
      ) : null}

      {canSubmit ? (
        <div className="space-y-2.5 border-t pt-4">
          <div>
            <h3 className="text-body-sm font-semibold">Trước khi gửi duyệt</h3>
            <p className="text-caption text-muted-foreground">
              Gợi ý, không bắt buộc · {curriculum.isPending ? "…" : `${done}/${checks.length}`}
            </p>
          </div>
          <ul className="space-y-2">
            {checks.map((check) => (
              <li key={check.label} className="flex items-start gap-2.5 text-body-sm">
                {check.done ? (
                  <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-success" aria-hidden />
                ) : (
                  <Circle className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
                )}
                <span className={check.done ? undefined : "text-muted-foreground"}>
                  {check.label}
                  <span className="sr-only">{check.done ? ": đã có" : ": chưa có"}</span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
