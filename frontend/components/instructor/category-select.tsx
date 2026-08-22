"use client";

import { useQuery } from "@tanstack/react-query";
import { useId } from "react";

import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { listCategories } from "@/lib/api/categories";

/**
 * The category picker.
 *
 * The taxonomy is two levels deep, so a parent with children becomes an
 * `<optgroup>` and only the leaves are selectable -- "Lập trình web" as a
 * course category says less than "Frontend" does. A parent with no children yet
 * stays selectable on its own, otherwise a fresh category would be unusable
 * until someone nested something under it.
 */
export function CategorySelect({
  value,
  onChange,
  disabled,
  error,
}: {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  error?: string | null;
}) {
  const id = useId();
  const messageId = `${id}-message`;
  const query = useQuery({ queryKey: ["categories"], queryFn: listCategories });

  const message = error ?? (query.isError ? "Không tải được danh mục." : null);

  // A course seeded straight into the database can sit on a category this list
  // does not offer -- a parent that has since grown children, say. Without a
  // matching option the select would render blank and look like "chưa chọn".
  const offered = (query.data ?? []).flatMap((parent) =>
    parent.children.length > 0
      ? parent.children.map((child) => child.id)
      : [parent.id],
  );
  const valueIsMissing = value !== "" && query.isSuccess && !offered.includes(value);

  return (
    <div className="space-y-2">
      <Label htmlFor={id}>Danh mục</Label>
      <NativeSelect
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled || query.isPending}
        aria-invalid={Boolean(message)}
        aria-describedby={message ? messageId : undefined}
      >
        <option value="">
          {query.isPending ? "Đang tải danh mục…" : "— Chọn danh mục —"}
        </option>
        {valueIsMissing ? (
          <option value={value}>Danh mục hiện tại (không còn trong danh sách)</option>
        ) : null}
        {(query.data ?? []).map((parent) =>
          parent.children.length > 0 ? (
            <optgroup key={parent.id} label={parent.name}>
              {parent.children.map((child) => (
                <option key={child.id} value={child.id}>
                  {child.name}
                </option>
              ))}
            </optgroup>
          ) : (
            <option key={parent.id} value={parent.id}>
              {parent.name}
            </option>
          ),
        )}
      </NativeSelect>
      {message ? (
        <p id={messageId} className="text-sm text-destructive">
          {message}
        </p>
      ) : null}
    </div>
  );
}
