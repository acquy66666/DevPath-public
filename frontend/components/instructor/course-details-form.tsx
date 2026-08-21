"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, Loader2 } from "lucide-react";
import { useId, useState, type FormEvent } from "react";

import { CategorySelect } from "@/components/instructor/category-select";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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

const LEVELS: Array<{ value: CourseLevel; label: string }> = [
  { value: "beginner", label: "Người mới bắt đầu" },
  { value: "intermediate", label: "Trung cấp" },
  { value: "advanced", label: "Nâng cao" },
];

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
    <Card>
      <CardHeader>
        <CardTitle>Thông tin khóa học</CardTitle>
        <CardDescription>
          Đây là những gì học viên thấy trước khi quyết định đăng ký.
        </CardDescription>
      </CardHeader>

      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          {mutation.isError ? (
            <Alert variant="destructive">
              <AlertDescription>{apiErrorMessage(mutation.error)}</AlertDescription>
            </Alert>
          ) : null}

          {mutation.isSuccess ? (
            <Alert>
              <AlertDescription className="flex items-center gap-2">
                <Check className="size-4" aria-hidden />
                Đã lưu thay đổi.
              </AlertDescription>
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

          <div className="space-y-2">
            <Label htmlFor={descriptionId}>Mô tả chi tiết</Label>
            <Textarea
              id={descriptionId}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              rows={6}
              placeholder="Học viên sẽ làm được gì sau khóa học, cần biết trước những gì…"
              disabled={mutation.isPending}
            />
            <p className="text-sm text-muted-foreground">
              Viết được bằng Markdown — trang chi tiết khóa học sẽ hiển thị đúng định
              dạng.
            </p>
          </div>

          <CategorySelect
            value={categoryId}
            onChange={setCategoryId}
            error={errors.category}
            disabled={mutation.isPending}
          />

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor={levelId}>Trình độ</Label>
              <NativeSelect
                id={levelId}
                value={level}
                onChange={(event) => setLevel(event.target.value as CourseLevel)}
                disabled={mutation.isPending}
              >
                {LEVELS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
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
              hint="Nhập 0 nếu khóa học miễn phí."
              disabled={mutation.isPending}
            />
          </div>

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
        </form>
      </CardContent>
    </Card>
  );
}
