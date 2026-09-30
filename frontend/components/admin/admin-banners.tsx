"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, ImagePlus, Loader2, Pencil, Plus, Trash2 } from "lucide-react";
import { useId, useState, type FormEvent } from "react";

import { ADMIN_KEY } from "@/components/admin/admin-nav";
import { EmptyState, ListSkeleton } from "@/components/admin/admin-shared";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { FormField } from "@/components/ui/form-field";
import { Label } from "@/components/ui/label";
import {
  createBanner,
  createBannerUpload,
  deleteBanner,
  listAdminBanners,
  reorderBanners,
  updateBanner,
  type AdminBanner,
  type BannerInput,
  type BannerStatus,
} from "@/lib/api/admin";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { UploadError, uploadToStorage } from "@/lib/api/storage";
import { useAuth } from "@/lib/auth/auth-provider";
import { formatDate } from "@/lib/format";

const BANNERS_KEY = [...ADMIN_KEY, "banners"] as const;
const TITLE_MAX_LENGTH = 120;
const IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"];
const MAX_BYTES = 8 * 1024 * 1024;

const STATUS: Record<BannerStatus, { label: string; variant: "default" | "secondary" | "outline" }> = {
  live: { label: "Đang hiện", variant: "default" },
  scheduled: { label: "Chờ tới lịch", variant: "outline" },
  ended: { label: "Hết lịch", variant: "secondary" },
  off: { label: "Đang tắt", variant: "secondary" },
};

/**
 * The banners across the top of the homepage. Order here is order there; the
 * homepage shows the first five that are switched on and inside their window.
 */
export function AdminBanners() {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<AdminBanner | "new" | null>(null);

  const banners = useQuery({
    queryKey: BANNERS_KEY,
    queryFn: () => listAdminBanners(accessToken as string),
    enabled: accessToken !== null,
  });

  const reorder = useMutation({
    mutationFn: (ids: string[]) => reorderBanners(accessToken as string, ids),
    onSuccess: (next) => queryClient.setQueryData(BANNERS_KEY, next),
  });

  function move(index: number, step: -1 | 1) {
    const ids = (banners.data ?? []).map((banner) => banner.id);
    const target = index + step;
    if (target < 0 || target >= ids.length) return;
    [ids[index], ids[target]] = [ids[target], ids[index]];
    reorder.mutate(ids);
  }

  const items = banners.data ?? [];

  return (
    <section className="space-y-4" aria-labelledby="admin-banners-title">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 id="admin-banners-title" className="font-semibold">
            Banner trang chủ
          </h2>
          <p className="text-sm text-muted-foreground">
            Trang chủ xoay vòng tối đa 5 banner đang bật và trong lịch, theo thứ tự dưới đây.
          </p>
        </div>
        <Button onClick={() => setEditing("new")}>
          <Plus aria-hidden />
          Thêm banner
        </Button>
      </div>

      {banners.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(banners.error)}</AlertDescription>
        </Alert>
      ) : null}
      {reorder.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(reorder.error)}</AlertDescription>
        </Alert>
      ) : null}
      {banners.isPending ? <ListSkeleton height="h-28" /> : null}
      {banners.data && items.length === 0 ? (
        <EmptyState
          icon={ImagePlus}
          title="Chưa có banner nào"
          hint="Banner hiện ở đầu trang chủ — dùng cho khóa học mới, mã giảm giá, sự kiện. Ảnh ngang, tỉ lệ khoảng 21:8."
        />
      ) : null}

      <ul className="space-y-3" aria-busy={reorder.isPending}>
        {items.map((banner, index) => (
          <li key={banner.id}>
            <BannerRow
              banner={banner}
              first={index === 0}
              last={index === items.length - 1}
              busy={reorder.isPending}
              onMove={(step) => move(index, step)}
              onEdit={() => setEditing(banner)}
            />
          </li>
        ))}
      </ul>

      <Dialog open={editing !== null} onOpenChange={(open) => (open ? null : setEditing(null))}>
        <DialogContent className="max-w-xl">
          {editing !== null ? (
            <BannerForm
              key={editing === "new" ? "new" : editing.id}
              banner={editing === "new" ? null : editing}
              onDone={() => setEditing(null)}
            />
          ) : null}
        </DialogContent>
      </Dialog>
    </section>
  );
}

function BannerRow({
  banner,
  first,
  last,
  busy,
  onMove,
  onEdit,
}: {
  banner: AdminBanner;
  first: boolean;
  last: boolean;
  busy: boolean;
  onMove: (step: -1 | 1) => void;
  onEdit: () => void;
}) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const [confirming, setConfirming] = useState(false);
  const refresh = () => queryClient.invalidateQueries({ queryKey: BANNERS_KEY });

  const toggle = useMutation({
    mutationFn: () =>
      updateBanner(accessToken as string, banner.id, { is_active: !banner.is_active }),
    onSuccess: refresh,
  });
  const remove = useMutation({
    mutationFn: () => deleteBanner(accessToken as string, banner.id),
    onSuccess: refresh,
  });
  const error = toggle.error ?? remove.error;
  const { label, variant } = STATUS[banner.status];

  return (
    <div className="space-y-2 rounded-xl border p-3">
      <div className="flex flex-wrap gap-3">
        {/* eslint-disable-next-line @next/next/no-img-element -- R2/MinIO URLs, not optimisable here */}
        <img
          src={banner.image_url}
          alt=""
          className="aspect-[21/8] w-full rounded-lg border object-cover sm:w-56"
        />
        <div className="min-w-0 flex-1 space-y-1">
          <p className="flex flex-wrap items-center gap-2">
            <span className="font-medium break-words">{banner.title}</span>
            <Badge variant={variant}>{label}</Badge>
          </p>
          <p className="truncate text-sm text-muted-foreground">
            {banner.link_url ? `Dẫn tới ${banner.link_url}` : "Không có liên kết"}
          </p>
          <p className="text-xs text-muted-foreground">
            {banner.starts_at ? `Hiện từ ${formatDate(banner.starts_at)}` : "Hiện ngay khi bật"}
            {banner.ends_at ? ` · gỡ lúc ${formatDate(banner.ends_at)}` : " · không hạn"}
          </p>
          <div className="flex flex-wrap items-center gap-1 pt-1">
            <Button variant="outline" size="sm" onClick={() => toggle.mutate()} disabled={toggle.isPending}>
              {toggle.isPending ? <Loader2 className="animate-spin" aria-hidden /> : null}
              {banner.is_active ? "Tắt" : "Bật"}
            </Button>
            <Button variant="ghost" size="icon" className="size-8" aria-label={`Đưa “${banner.title}” lên`} disabled={first || busy} onClick={() => onMove(-1)}>
              <ArrowUp aria-hidden />
            </Button>
            <Button variant="ghost" size="icon" className="size-8" aria-label={`Đưa “${banner.title}” xuống`} disabled={last || busy} onClick={() => onMove(1)}>
              <ArrowDown aria-hidden />
            </Button>
            <Button variant="ghost" size="icon" className="size-8" aria-label={`Sửa “${banner.title}”`} onClick={onEdit}>
              <Pencil aria-hidden />
            </Button>
            <Button variant="ghost" size="icon" className="size-8" aria-label={`Xóa “${banner.title}”`} onClick={() => setConfirming(true)}>
              <Trash2 aria-hidden />
            </Button>
          </div>
        </div>
      </div>
      {confirming ? (
        <div className="flex flex-wrap items-center gap-2 rounded-lg bg-destructive/5 p-2 text-sm">
          <span className="min-w-0 flex-1">Xóa banner “{banner.title}” và ảnh của nó?</span>
          <Button size="sm" variant="destructive" onClick={() => remove.mutate()} disabled={remove.isPending}>
            {remove.isPending ? <Loader2 className="animate-spin" aria-hidden /> : null}
            Xóa
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setConfirming(false)}>
            Hủy
          </Button>
        </div>
      ) : null}
      {error ? <p className="text-sm text-destructive">{apiErrorMessage(error)}</p> : null}
    </div>
  );
}

function toLocalInput(iso: string | null): string {
  if (!iso) return "";
  const date = new Date(iso);
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function fromLocalInput(value: string): string | null {
  return value ? new Date(value).toISOString() : null;
}

function BannerForm({ banner, onDone }: { banner: AdminBanner | null; onDone: () => void }) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const fileId = useId();

  const [title, setTitle] = useState(banner?.title ?? "");
  const [link, setLink] = useState(banner?.link_url ?? "");
  const [active, setActive] = useState(banner?.is_active ?? true);
  const [startsAt, setStartsAt] = useState(toLocalInput(banner?.starts_at ?? null));
  const [endsAt, setEndsAt] = useState(toLocalInput(banner?.ends_at ?? null));
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(banner?.image_url ?? null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [progress, setProgress] = useState<number | null>(null);

  function pick(next: File | null) {
    setFileError(null);
    if (!next) return;
    if (!IMAGE_TYPES.includes(next.type)) {
      setFileError("Chỉ nhận ảnh JPEG, PNG hoặc WebP.");
      return;
    }
    if (next.size > MAX_BYTES) {
      setFileError("Ảnh banner tối đa 8 MB.");
      return;
    }
    setFile(next);
    setPreview(URL.createObjectURL(next));
  }

  const save = useMutation({
    mutationFn: async () => {
      let imageKey: string | undefined;
      if (file) {
        const ticket = await createBannerUpload(accessToken as string, {
          filename: file.name,
          content_type: file.type,
          size_bytes: file.size,
        });
        setProgress(0);
        await uploadToStorage(ticket, file, setProgress);
        imageKey = ticket.storage_key;
      }
      const body: BannerInput = {
        title: title.trim(),
        link_url: link.trim() || null,
        is_active: active,
        starts_at: fromLocalInput(startsAt),
        ends_at: fromLocalInput(endsAt),
      };
      return banner
        ? updateBanner(accessToken as string, banner.id, { ...body, image_key: imageKey })
        : createBanner(accessToken as string, { ...body, image_key: imageKey as string });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: BANNERS_KEY });
      onDone();
    },
    onSettled: () => setProgress(null),
  });

  const invalid = title.trim() === "" || (!banner && !file);

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!invalid) save.mutate();
  }

  return (
    <form onSubmit={submit} className="grid gap-4">
      <DialogHeader>
        <DialogTitle>{banner ? "Sửa banner" : "Thêm banner"}</DialogTitle>
        <DialogDescription>
          Ảnh ngang (khoảng 21:8), tiêu đề hiện đè lên phần dưới ảnh.
        </DialogDescription>
      </DialogHeader>

      <div className="space-y-2">
        <Label htmlFor={fileId}>Ảnh</Label>
        {preview ? (
          // eslint-disable-next-line @next/next/no-img-element -- a local blob or a bucket URL
          <img src={preview} alt="" className="aspect-[21/8] w-full rounded-lg border object-cover" />
        ) : null}
        <input
          id={fileId}
          type="file"
          accept={IMAGE_TYPES.join(",")}
          onChange={(event) => pick(event.target.files?.[0] ?? null)}
          className="block w-full text-sm file:mr-3 file:rounded-md file:border file:bg-background file:px-3 file:py-1.5 file:text-sm"
        />
        {fileError ? <p className="text-sm text-destructive">{fileError}</p> : null}
        {progress !== null ? (
          <p className="text-sm text-muted-foreground">Đang tải ảnh lên… {progress}%</p>
        ) : null}
      </div>

      <FormField label="Tiêu đề" type="text" value={title} onChange={(next) => setTitle(next.slice(0, TITLE_MAX_LENGTH))} placeholder="VD: Giảm 30% mọi khóa Python đến hết tháng" />
      <FormField
        label="Liên kết (không bắt buộc)"
        type="text"
        value={link}
        onChange={setLink}
        placeholder="/khoa-hoc?q=python hoặc https://…"
        hint="Đường dẫn trong trang bắt đầu bằng /, hoặc địa chỉ http(s)."
      />

      <div className="grid gap-4 sm:grid-cols-2">
        <FormField label="Bắt đầu hiện" type="datetime-local" value={startsAt} onChange={setStartsAt} hint="Trống: ngay khi bật" />
        <FormField label="Gỡ lúc" type="datetime-local" value={endsAt} onChange={setEndsAt} hint="Trống: không hạn" />
      </div>

      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" className="size-4 accent-primary" checked={active} onChange={(event) => setActive(event.target.checked)} />
        Bật banner
      </label>

      {save.isError ? (
        <Alert variant="destructive">
          <AlertDescription>
            {save.error instanceof UploadError ? save.error.message : apiErrorMessage(save.error)}
          </AlertDescription>
        </Alert>
      ) : null}

      <DialogFooter>
        <Button type="button" variant="ghost" onClick={onDone}>
          Hủy
        </Button>
        <Button type="submit" disabled={invalid || save.isPending}>
          {save.isPending ? <Loader2 className="animate-spin" aria-hidden /> : null}
          {banner ? "Lưu thay đổi" : "Thêm banner"}
        </Button>
      </DialogFooter>
    </form>
  );
}
