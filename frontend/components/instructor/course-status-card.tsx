"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

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
import {
  deleteCourse,
  submitCourse,
  unpublishCourse,
  type Course,
} from "@/lib/api/courses";
import { useAuth } from "@/lib/auth/auth-provider";

const EXPLANATION: Record<Course["status"], string> = {
  draft: "Chỉ mình bạn thấy khóa học này. Gửi duyệt để đưa nó ra ngoài.",
  pending_review: "Khóa học đang chờ quản trị viên duyệt.",
  published: "Khóa học đang hiển thị công khai và nhận học viên.",
  rejected: "Khóa học bị từ chối. Sửa nội dung rồi gửi duyệt lại.",
};

export function CourseStatusCard({ course }: { course: Course }) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const router = useRouter();
  const [confirmingDelete, setConfirmingDelete] = useState(false);

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

  const remove = useMutation({
    mutationFn: () => deleteCourse(accessToken as string, course.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["my-courses"] });
      router.push("/giang-day");
    },
  });

  const error = submit.error ?? unpublish.error ?? remove.error;
  const canSubmit = course.status === "draft" || course.status === "rejected";

  return (
    <Card>
      <CardHeader>
        <CardTitle>Trạng thái</CardTitle>
        <CardDescription>{EXPLANATION[course.status]}</CardDescription>
      </CardHeader>

      <CardContent className="space-y-4">
        {error ? (
          <Alert variant="destructive">
            <AlertDescription>{apiErrorMessage(error)}</AlertDescription>
          </Alert>
        ) : null}

        <div className="flex flex-wrap gap-2">
          {canSubmit ? (
            <Button onClick={() => submit.mutate()} disabled={submit.isPending}>
              {submit.isPending ? (
                <>
                  <Loader2 className="animate-spin" aria-hidden />
                  Đang gửi…
                </>
              ) : (
                "Gửi duyệt"
              )}
            </Button>
          ) : null}

          {course.status === "published" ? (
            <Button
              variant="outline"
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
        </div>

        <div className="rounded-lg border border-destructive/30 p-4">
          <p className="text-sm font-medium">Xóa khóa học</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Khóa học biến mất khỏi danh sách của bạn và khỏi trang công khai. Học viên
            đã mua vẫn xem tiếp được — đó là lý do dữ liệu không bị xóa hẳn.
          </p>

          {confirmingDelete ? (
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <span className="text-sm font-medium">Xóa &quot;{course.title}&quot;?</span>
              <Button
                variant="destructive"
                size="sm"
                onClick={() => remove.mutate()}
                disabled={remove.isPending}
              >
                {remove.isPending ? (
                  <>
                    <Loader2 className="animate-spin" aria-hidden />
                    Đang xóa…
                  </>
                ) : (
                  "Xóa hẳn"
                )}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setConfirmingDelete(false)}
                disabled={remove.isPending}
              >
                Hủy
              </Button>
            </div>
          ) : (
            <Button
              variant="outline"
              size="sm"
              className="mt-3"
              onClick={() => setConfirmingDelete(true)}
            >
              <Trash2 aria-hidden />
              Xóa khóa học
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
