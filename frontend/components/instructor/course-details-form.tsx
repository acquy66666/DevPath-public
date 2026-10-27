"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, Loader2 } from "lucide-react";
import { useId, useState, type FormEvent } from "react";

import { CategorySelect } from "@/components/instructor/category-select";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { FormField } from "@/components/ui/form-field";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { Textarea } from "@/components/ui/textarea";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { updateCourse, type Course, type CourseLevel } from "@/lib/api/courses";
import { useAuth } from "@/lib/auth/auth-provider";
import {
  validateCourseTitle,
  validatePrice,
  validateSubtitle,
} from "@/lib/courses/validation";
import { LEVEL_LABELS, LEVEL_ORDER } from "@/lib/courses/labels";

export function CourseDetailsForm({ course }: { course: Course }) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const levelId = useId();
  const descriptionId = useId();

  const [title, setTitle] = useState(course.title);
  const [subtitle, setSubtitle] = useState(course.subtitle ?? "");
  const [description, setDescription] = useState(course.description ?? "");
  const [categoryId, setCategoryId] = useState(course.category_id);
  const [level, setLevel] = useState<CourseLevel>(course.level);
  // Trailing ".00" is how NUMERIC comes back; nobody wants to edit around it.
  const [price, setPrice] = useState(course.price.replace(/\.00$/, ""));

  const [errors, setErrors] = useState<Record<string, string | null>>({});

  const mutation = useMutation({
    mutationFn: () =>
      updateCourse(accessToken as string, course.id, {
        title: title.trim(),
        subtitle: subtitle.trim() || null,
        description: description.trim() || null,
        category_id: categoryId,
        level,
        price: price.trim(),
      }),
    onSuccess: (updated) => {
      // The heading above this form reads the same query.
      queryClient.setQueryData(["course", course.id], updated);
      queryClient.invalidateQueries({ queryKey: ["my-courses"] });
    },
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const next = {
      title: validateCourseTitle(title),
      subtitle: validateSubtitle(subtitle),
      price: validatePrice(price),
      category: categoryId ? null : "Vui lòng chọn danh mục",
    };
    setErrors(next);
    if (Object.values(next).some(Boolean)) return;

    mutation.mutate();
  }

  return (
    <section aria-labelledby="course-details" className="rounded-lg border bg-card p-5 sm:p-6">
      <h2 id="course-details" className="text-h3">
        Học viên thấy gì trước khi đăng ký
      </h2>
      <p className="mt-1 text-body-sm text-muted-foreground">
        Tên, mô tả và giá hiện trên thẻ khóa học và trang chi tiết.
      </p>

      <form onSubmit={handleSubmit} className="mt-5 space-y-5" noValidate>
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
          error={errors.title}
          disabled={mutation.isPending}
        />

        <FormField
          label="Mô tả ngắn"
          type="text"
          value={subtitle}
          onChange={setSubtitle}
          error={errors.subtitle}
          placeholder="Một câu tóm tắt khóa học dạy được điều gì"
          disabled={mutation.isPending}
        />

        <div className="space-y-1.5">
          <Label htmlFor={descriptionId}>
            Mô tả chi tiết <span className="font-normal text-muted-foreground">· Markdown</span>
          </Label>
          <Textarea
            id={descriptionId}
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            rows={7}
            placeholder="Học viên sẽ làm được gì sau khóa học, cần biết trước những gì…"
            aria-describedby={`${descriptionId}-hint`}
            disabled={mutation.isPending}
          />
          <p id={`${descriptionId}-hint`} className="text-sm text-muted-foreground">
            Học viên sẽ làm được gì, cần biết trước những gì. Trang chi tiết hiện đúng định dạng.
          </p>
        </div>

        <div className="grid gap-5 sm:grid-cols-3 sm:gap-4">
          <CategorySelect
            value={categoryId}
            onChange={setCategoryId}
            error={errors.category}
            disabled={mutation.isPending}
          />

          <div className="space-y-2">
            <Label htmlFor={levelId}>Trình độ</Label>
            <NativeSelect
              id={levelId}
              value={level}
              onChange={(event) => setLevel(event.target.value as CourseLevel)}
              disabled={mutation.isPending}
            >
              {LEVEL_ORDER.map((value) => (
                <option key={value} value={value}>
                  {LEVEL_LABELS[value]}
                </option>
              ))}
            </NativeSelect>
          </div>

          <FormField
            label="Giá (VND)"
            type="text"
            value={price}
            onChange={setPrice}
            error={errors.price}
            hint="0 là miễn phí."
            disabled={mutation.isPending}
          />
        </div>

        <div className="flex flex-wrap items-center gap-3 border-t pt-5">
          <Button type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? (
              <>
                <Loader2 className="animate-spin" aria-hidden />
                Đang lưu…
              </>
            ) : (
              "Lưu thay đổi"
            )}
          </Button>
          <p role="status" className="flex items-center gap-1.5 text-body-sm text-success-text">
            {mutation.isSuccess && !mutation.isPending ? (
              <>
                <Check className="size-4" aria-hidden />
                Đã lưu thay đổi.
              </>
            ) : null}
          </p>
        </div>
      </form>
    </section>
  );
}
