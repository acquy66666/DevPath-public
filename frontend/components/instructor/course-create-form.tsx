"use client";

import { useMutation } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { CategorySelect } from "@/components/instructor/category-select";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { FormField } from "@/components/ui/form-field";
import { createCourse } from "@/lib/api/courses";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { useAuth } from "@/lib/auth/auth-provider";
import { validateCourseTitle } from "@/lib/courses/validation";

export function CourseCreateForm() {
  const router = useRouter();
  const { accessToken } = useAuth();

  const [title, setTitle] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [titleError, setTitleError] = useState<string | null>(null);
  const [categoryError, setCategoryError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      createCourse(accessToken as string, {
        title: title.trim(),
        category_id: categoryId,
      }),
    onSuccess: (course) => {
      // Straight into the editor: an empty course on the list page is a dead
      // end, and the next thing anyone wants is the curriculum.
      router.push(`/giang-day/${course.id}`);
    },
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const nextTitleError = validateCourseTitle(title);
    const nextCategoryError = categoryId ? null : "Vui lòng chọn danh mục";
    setTitleError(nextTitleError);
    setCategoryError(nextCategoryError);
    if (nextTitleError || nextCategoryError) return;

    mutation.mutate();
  }

  // Kept pending through the redirect: the router push resolves before the new
  // page paints, and a button that springs back to "Tạo khóa học" invites a
  // second click and a second course.
  const busy = mutation.isPending || mutation.isSuccess;

  return (
    <Card>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          {mutation.isError ? (
            <Alert variant="destructive">
              <AlertDescription>{apiErrorMessage(mutation.error)}</AlertDescription>
            </Alert>
          ) : null}

          <FormField
            label="Tên khóa học"
            type="text"
            value={title}
            onChange={setTitle}
            error={titleError}
            placeholder="Ví dụ: Lập trình Python cơ bản"
            hint="Đổi tên lúc nào cũng được — đường dẫn khóa học giữ nguyên."
            disabled={busy}
            autoFocus
          />

          <CategorySelect
            value={categoryId}
            onChange={(next) => {
              setCategoryId(next);
              setCategoryError(null);
            }}
            error={categoryError}
            disabled={busy}
          />

          <Button type="submit" disabled={busy}>
            {busy ? (
              <>
                <Loader2 className="animate-spin" aria-hidden />
                Đang tạo…
              </>
            ) : (
              "Tạo khóa học"
            )}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
