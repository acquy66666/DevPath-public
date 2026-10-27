"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { deleteCourse, type Course } from "@/lib/api/courses";
import { useAuth } from "@/lib/auth/auth-provider";

/**
 * Deleting the course, at the foot of its details: rare, and asked twice.
 * The course is soft-deleted -- learners who bought it keep learning.
 */
export function CourseDeleteCard({ course }: { course: Course }) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const router = useRouter();
  const [confirming, setConfirming] = useState(false);

  const remove = useMutation({
    mutationFn: () => deleteCourse(accessToken as string, course.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["my-courses"] });
      router.push("/giang-day");
    },
  });

  return (
    <section
      aria-labelledby="delete-course"
      className="space-y-3 rounded-lg border border-destructive/30 bg-card p-5 sm:px-6"
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="flex-1">
          <h2 id="delete-course" className="text-body font-semibold">
            Xóa khóa học
          </h2>
          <p className="text-body-sm text-muted-foreground">
            Biến mất khỏi danh sách của bạn và trang công khai. Học viên đã mua vẫn học tiếp được, nên
            dữ liệu không bị xóa hẳn.
          </p>
        </div>
        {confirming ? null : (
          <Button
            variant="outline"
            className="self-start text-destructive-text sm:self-auto"
            onClick={() => setConfirming(true)}
          >
            <Trash2 aria-hidden />
            Xóa khóa học
          </Button>
        )}
      </div>

      {confirming ? (
        <div className="flex flex-wrap items-center gap-2 rounded-md bg-destructive-soft px-3 py-2.5">
          <span className="text-body-sm font-medium">Xóa “{course.title}”?</span>
          <Button variant="destructive" size="sm" onClick={() => remove.mutate()} disabled={remove.isPending}>
            {remove.isPending ? (
              <>
                <Loader2 className="animate-spin" aria-hidden />
                Đang xóa…
              </>
            ) : (
              "Xóa hẳn"
            )}
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setConfirming(false)} disabled={remove.isPending}>
            Hủy
          </Button>
        </div>
      ) : null}

      {remove.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(remove.error)}</AlertDescription>
        </Alert>
      ) : null}
    </section>
  );
}
