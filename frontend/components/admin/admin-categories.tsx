"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, Loader2, Pencil, Plus, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";

import { ADMIN_KEY } from "@/components/admin/admin-nav";
import { EmptyState, ListSkeleton } from "@/components/admin/admin-shared";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import {
  createCategory,
  deleteCategory,
  listAdminCategories,
  reorderCategories,
  updateCategory,
  type AdminCategory,
  type AdminCategoryTree,
} from "@/lib/api/admin";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { useAuth } from "@/lib/auth/auth-provider";

const CATEGORIES_KEY = [...ADMIN_KEY, "categories"] as const;
const NAME_MAX_LENGTH = 100;

/**
 * The taxonomy instructors file courses under and the catalogue filters by.
 *
 * Two levels, as the backend enforces. Order is changed a step at a time with
 * the arrows, but what is sent is the whole level -- the same "send the final
 * order" rule as the curriculum builder.
 */
export function AdminCategories() {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();

  const tree = useQuery({
    queryKey: CATEGORIES_KEY,
    queryFn: () => listAdminCategories(accessToken as string),
    enabled: accessToken !== null,
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: CATEGORIES_KEY });
    // The course form and the catalogue read the public list.
    queryClient.invalidateQueries({ queryKey: ["categories"] });
  };

  const reorder = useMutation({
    mutationFn: ({ parentId, ids }: { parentId: string | null; ids: string[] }) =>
      reorderCategories(accessToken as string, parentId, ids),
    onSuccess: (next) => {
      queryClient.setQueryData(CATEGORIES_KEY, next);
      queryClient.invalidateQueries({ queryKey: ["categories"] });
    },
  });

  function move(level: AdminCategory[], parentId: string | null, index: number, step: -1 | 1) {
    const ids = level.map((category) => category.id);
    const target = index + step;
    if (target < 0 || target >= ids.length) return;
    [ids[index], ids[target]] = [ids[target], ids[index]];
    reorder.mutate({ parentId, ids });
  }

  const parents = tree.data ?? [];

  return (
    <section className="space-y-4" aria-labelledby="admin-categories-title">
      <div>
        <h1 id="admin-categories-title" className="text-h2 text-pretty sm:text-h1">
          Danh mục khóa học
        </h1>
        <p className="mt-1 max-w-3xl text-body text-pretty text-muted-foreground">
          Hai cấp. Giảng viên chọn danh mục khi tạo khóa học, trang danh sách khóa học lọc theo
          đây. Chỉ xóa được danh mục trống.
        </p>
      </div>

      <AddCategory parentId={null} label="Thêm danh mục cấp trên cùng" onAdded={refresh} />

      {tree.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(tree.error)}</AlertDescription>
        </Alert>
      ) : null}
      {reorder.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(reorder.error)}</AlertDescription>
        </Alert>
      ) : null}

      {tree.isPending ? <ListSkeleton height="h-28" fill /> : null}

      {tree.data && parents.length === 0 ? (
        <EmptyState
          title="Chưa có danh mục nào"
          hint="Tạo danh mục cấp trên cùng trước, rồi thêm danh mục con vào bên trong."
        />
      ) : null}

      <ul className="space-y-3" aria-busy={reorder.isPending}>
        {parents.map((parent, index) => (
          <li key={parent.id} className="overflow-hidden rounded-lg border bg-card">
            <CategoryRow
              category={parent}
              parents={parents}
              first={index === 0}
              last={index === parents.length - 1}
              busy={reorder.isPending}
              onMove={(step) => move(parents, null, index, step)}
              onChanged={refresh}
            />
            <div className="space-y-1 border-t bg-muted px-3 py-2 sm:pl-10">
              {parent.children.length > 0 ? (
                <ul className="space-y-1">
                  {parent.children.map((child, childIndex) => (
                    <li key={child.id}>
                      <CategoryRow
                        category={child}
                        parents={parents}
                        first={childIndex === 0}
                        last={childIndex === parent.children.length - 1}
                        busy={reorder.isPending}
                        onMove={(step) => move(parent.children, parent.id, childIndex, step)}
                        onChanged={refresh}
                        nested
                      />
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="px-1 py-1 text-sm text-muted-foreground">Chưa có danh mục con.</p>
              )}
              <AddCategory parentId={parent.id} label="Thêm danh mục con" onAdded={refresh} compact />
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

function AddCategory({
  parentId,
  label,
  onAdded,
  compact = false,
}: {
  parentId: string | null;
  label: string;
  onAdded: () => void;
  compact?: boolean;
}) {
  const { accessToken } = useAuth();
  const [open, setOpen] = useState(!compact);
  const [name, setName] = useState("");

  const add = useMutation({
    mutationFn: () => createCategory(accessToken as string, { name: name.trim(), parent_id: parentId }),
    onSuccess: () => {
      setName("");
      if (compact) setOpen(false);
      onAdded();
    },
  });

  if (!open) {
    return (
      <Button variant="ghost" size="sm" className="text-muted-foreground" onClick={() => setOpen(true)}>
        <Plus aria-hidden />
        {label}
      </Button>
    );
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    if (name.trim()) add.mutate();
  }

  return (
    <form onSubmit={submit} className="space-y-2">
      <div className="flex gap-2">
        <label className="sr-only" htmlFor={`new-category-${parentId ?? "top"}`}>
          {label}
        </label>
        <Input
          id={`new-category-${parentId ?? "top"}`}
          value={name}
          onChange={(event) => setName(event.target.value)}
          maxLength={NAME_MAX_LENGTH}
          placeholder={parentId ? "Tên danh mục con" : "Tên danh mục mới, ví dụ: Khoa học dữ liệu"}
         
          autoFocus={compact}
        />
        <Button type="submit" disabled={add.isPending || name.trim() === ""}>
          {add.isPending ? <Loader2 className="animate-spin" aria-hidden /> : <Plus aria-hidden />}
          <span className="hidden sm:inline">Thêm</span>
        </Button>
        {compact ? (
          <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
            Hủy
          </Button>
        ) : null}
      </div>
      {add.isError ? (
        <p className="text-sm text-destructive">{apiErrorMessage(add.error)}</p>
      ) : null}
    </form>
  );
}

function CategoryRow({
  category,
  parents,
  first,
  last,
  busy,
  onMove,
  onChanged,
  nested = false,
}: {
  category: AdminCategoryTree | AdminCategory;
  parents: AdminCategoryTree[];
  first: boolean;
  last: boolean;
  busy: boolean;
  onMove: (step: -1 | 1) => void;
  onChanged: () => void;
  nested?: boolean;
}) {
  const { accessToken } = useAuth();
  const [editing, setEditing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [name, setName] = useState(category.name);
  const [parentId, setParentId] = useState(category.parent_id ?? "");

  const hasChildren = "children" in category && category.children.length > 0;

  const save = useMutation({
    mutationFn: () => {
      const body: { name?: string; parent_id?: string | null } = {};
      if (name.trim() !== category.name) body.name = name.trim();
      if ((parentId || null) !== category.parent_id) body.parent_id = parentId || null;
      return updateCategory(accessToken as string, category.id, body);
    },
    onSuccess: () => {
      setEditing(false);
      onChanged();
    },
  });

  const remove = useMutation({
    mutationFn: () => deleteCategory(accessToken as string, category.id),
    onSuccess: onChanged,
  });

  if (editing) {
    return (
      <form
        className="space-y-2 p-2"
        onSubmit={(event) => {
          event.preventDefault();
          if (name.trim()) save.mutate();
        }}
      >
        <div className="flex flex-wrap gap-2">
          <label className="sr-only" htmlFor={`name-${category.id}`}>
            Tên danh mục
          </label>
          <Input
            id={`name-${category.id}`}
            value={name}
            onChange={(event) => setName(event.target.value)}
            maxLength={NAME_MAX_LENGTH}
            className="min-w-0 flex-1 basis-48"
            autoFocus
          />
          <label className="sr-only" htmlFor={`parent-${category.id}`}>
            Nằm trong
          </label>
          <NativeSelect
            id={`parent-${category.id}`}
            className="w-auto max-w-56"
            value={parentId}
            onChange={(event) => setParentId(event.target.value)}
            disabled={hasChildren}
            title={hasChildren ? "Danh mục đang có danh mục con nên giữ ở cấp trên cùng" : undefined}
          >
            <option value="">— Cấp trên cùng —</option>
            {parents
              .filter((parent) => parent.id !== category.id)
              .map((parent) => (
                <option key={parent.id} value={parent.id}>
                  Trong: {parent.name}
                </option>
              ))}
          </NativeSelect>
        </div>
        {save.isError ? (
          <p className="text-sm text-destructive">{apiErrorMessage(save.error)}</p>
        ) : null}
        <div className="flex gap-2">
          <Button type="submit" size="sm" disabled={save.isPending || name.trim() === ""}>
            {save.isPending ? <Loader2 className="animate-spin" aria-hidden /> : null}
            Lưu
          </Button>
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={() => {
              setEditing(false);
              setName(category.name);
              setParentId(category.parent_id ?? "");
            }}
          >
            Hủy
          </Button>
        </div>
      </form>
    );
  }

  return (
    <div className={nested ? "px-1 py-1" : "p-3"}>
      <div className="flex flex-wrap items-center gap-2">
        <div className="min-w-0 flex-1">
          <p className={nested ? "text-sm break-words" : "font-medium break-words"}>{category.name}</p>
          <p className="text-xs text-muted-foreground">
            {category.slug} · {category.courses_count} khóa học
          </p>
        </div>
        <div className="flex items-center">
          <Button
            variant="ghost"
            size="icon"
            className="size-8"
            aria-label={`Đưa “${category.name}” lên`}
            disabled={first || busy}
            onClick={() => onMove(-1)}
          >
            <ArrowUp aria-hidden />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="size-8"
            aria-label={`Đưa “${category.name}” xuống`}
            disabled={last || busy}
            onClick={() => onMove(1)}
          >
            <ArrowDown aria-hidden />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="size-8"
            aria-label={`Sửa “${category.name}”`}
            onClick={() => setEditing(true)}
          >
            <Pencil aria-hidden />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="size-8"
            aria-label={`Xóa “${category.name}”`}
            onClick={() => setConfirming(true)}
          >
            <Trash2 aria-hidden />
          </Button>
        </div>
      </div>
      {confirming ? (
        <div className="mt-2 flex flex-wrap items-center gap-2 rounded-md bg-destructive-soft p-2 text-body-sm text-destructive-text">
          <span className="min-w-0 flex-1">Xóa danh mục “{category.name}”?</span>
          <Button
            size="sm"
            variant="destructive"
            onClick={() => remove.mutate()}
            disabled={remove.isPending}
          >
            {remove.isPending ? <Loader2 className="animate-spin" aria-hidden /> : null}
            Xóa
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              setConfirming(false);
              remove.reset();
            }}
          >
            Hủy
          </Button>
        </div>
      ) : null}
      {remove.isError ? (
        <p className="mt-1 text-sm text-destructive">{apiErrorMessage(remove.error)}</p>
      ) : null}
    </div>
  );
}
