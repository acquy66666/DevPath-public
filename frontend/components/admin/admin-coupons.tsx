"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Pencil, Plus, Trash2, X } from "lucide-react";
import { useId, useState, type FormEvent } from "react";

import { ADMIN_KEY } from "@/components/admin/admin-nav";
import { AdminTitle, EmptyState, ListSkeleton, SearchBox } from "@/components/admin/admin-shared";
import { FilterChips } from "@/components/admin/filter-chips";
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { Pager } from "@/components/ui/pager";
import {
  createCoupon,
  deleteCoupon,
  endCoupon,
  listAdminCourses,
  listAdminCoupons,
  updateCoupon,
  type AdminCoupon,
  type CouponFilter,
  type CouponInput,
  type CouponStatus,
} from "@/lib/api/admin";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { useAuth } from "@/lib/auth/auth-provider";
import { formatAmount, formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";

const COUPONS_KEY = [...ADMIN_KEY, "coupons"] as const;

const FILTERS: { value: CouponFilter; label: string }[] = [
  { value: "all", label: "Tất cả" },
  { value: "live", label: "Đang chạy" },
  { value: "scheduled", label: "Sắp chạy" },
  { value: "exhausted", label: "Hết lượt" },
  { value: "ended", label: "Đã kết thúc" },
];

const STATUS: Record<CouponStatus, { label: string; variant: "success" | "info" | "warning" | "muted" }> = {
  live: { label: "Đang chạy", variant: "success" },
  scheduled: { label: "Sắp chạy", variant: "info" },
  exhausted: { label: "Hết lượt", variant: "warning" },
  ended: { label: "Đã kết thúc", variant: "muted" },
};

function describeValue(coupon: Pick<AdminCoupon, "discount_type" | "value">): string {
  return coupon.discount_type === "percent"
    ? `Giảm ${Number(coupon.value)}%`
    : `Giảm ${formatAmount(coupon.value)}`;
}

/**
 * Site-wide campaigns. A code is made once and never renamed -- it is on
 * leaflets and in people's carts -- and everything else can change without
 * touching orders already placed. Ending early is the way to stop a code; a
 * used code is never deleted.
 */
export function AdminCoupons() {
  const { accessToken } = useAuth();
  const [status, setStatus] = useState<CouponFilter>("all");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<AdminCoupon | "new" | null>(null);

  const coupons = useQuery({
    queryKey: [...COUPONS_KEY, status, q, page],
    queryFn: () => listAdminCoupons(accessToken as string, { status, q, page }),
    enabled: accessToken !== null,
    placeholderData: keepPreviousData,
  });

  return (
    <section className="space-y-5" aria-labelledby="admin-coupons-title">
      <AdminTitle
        id="admin-coupons-title"
        title="Mã giảm giá"
        description="Học viên nhập mã ở giỏ hàng. Gõ mã không tiêu lượt; lượt chỉ tính khi đơn được thanh toán."
        actions={
          <Button onClick={() => setEditing("new")}>
            <Plus aria-hidden />
            Tạo mã
          </Button>
        }
      />

      <div className="flex flex-wrap items-center gap-3">
        <FilterChips
          label="Lọc theo trạng thái"
          value={status}
          onChange={(value) => {
            setStatus(value);
            setPage(1);
          }}
          options={FILTERS}
        />
        <SearchBox
          id="coupon-search"
          placeholder="Tìm theo mã"
          initial={q}
          onSearch={(value) => {
            setQ(value);
            setPage(1);
          }}
        />
      </div>

      {coupons.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(coupons.error)}</AlertDescription>
        </Alert>
      ) : null}
      {coupons.isPending ? <ListSkeleton height="h-20" fill /> : null}
      {coupons.data && coupons.data.total === 0 ? (
        <EmptyState
          mood={q || status !== "all" ? "empty-search" : "empty"}
          title={q || status !== "all" ? "Không có mã nào khớp" : "Chưa có mã giảm giá nào"}
          hint={
            q || status !== "all"
              ? "Đổi từ khóa tìm kiếm hoặc bộ lọc trạng thái."
              : "Bấm “Tạo mã” để mở một chiến dịch: giảm theo phần trăm hoặc số tiền, cho toàn sàn hoặc vài khóa học."
          }
        />
      ) : null}
      {coupons.data && coupons.data.items.length > 0 ? (
        <ul
          className={coupons.isPlaceholderData ? "space-y-2 opacity-60" : "space-y-2"}
          aria-busy={coupons.isFetching}
        >
          {coupons.data.items.map((coupon) => (
            <li key={coupon.id}>
              <CouponRow coupon={coupon} onEdit={() => setEditing(coupon)} />
            </li>
          ))}
        </ul>
      ) : null}
      {coupons.data ? (
        <Pager
          page={coupons.data.page}
          pageSize={coupons.data.page_size}
          total={coupons.data.total}
          onPage={setPage}
        />
      ) : null}

      <Dialog open={editing !== null} onOpenChange={(open) => (open ? null : setEditing(null))}>
        <DialogContent className="max-w-xl">
          {editing !== null ? (
            <CouponForm
              key={editing === "new" ? "new" : editing.id}
              coupon={editing === "new" ? null : editing}
              onDone={() => setEditing(null)}
            />
          ) : null}
        </DialogContent>
      </Dialog>
    </section>
  );
}

function CouponRow({ coupon, onEdit }: { coupon: AdminCoupon; onEdit: () => void }) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const [confirming, setConfirming] = useState<"end" | "delete" | null>(null);

  const settle = () => {
    setConfirming(null);
    queryClient.invalidateQueries({ queryKey: COUPONS_KEY });
  };
  const end = useMutation({
    mutationFn: () => endCoupon(accessToken as string, coupon.id),
    onSuccess: settle,
  });
  const remove = useMutation({
    mutationFn: () => deleteCoupon(accessToken as string, coupon.id),
    onSuccess: settle,
  });
  const error = end.error ?? remove.error;
  const { label, variant } = STATUS[coupon.status];

  return (
    <div
      className={cn(
        "space-y-2 rounded-lg border bg-card p-3 sm:p-4",
        coupon.status === "ended" && "bg-muted",
      )}
    >
      <div className="flex flex-wrap items-start gap-3">
        <div className="min-w-0 flex-1 space-y-1">
          <p className="flex flex-wrap items-center gap-2">
            <span className="rounded-sm bg-muted px-2 py-0.5 font-mono text-code font-semibold tracking-wide">
              {coupon.code}
            </span>
            <Badge variant={variant}>{label}</Badge>
            <span className="text-body-sm font-medium">{describeValue(coupon)}</span>
          </p>
          <p className="text-body-sm break-words text-muted-foreground">
            {coupon.scope === "site"
              ? "Toàn sàn"
              : `${coupon.courses.length} khóa: ${coupon.courses.map((c) => c.title).join(", ")}`}
          </p>
          <p className="text-caption text-muted-foreground">
            Từ {formatDate(coupon.valid_from)}
            {coupon.valid_to ? ` đến ${formatDate(coupon.valid_to)}` : " · không hạn kết thúc"}
          </p>
          <Uses coupon={coupon} />
        </div>
        <div className="flex items-center">
          <Button variant="ghost" size="icon" className="size-8" aria-label={`Sửa ${coupon.code}`} onClick={onEdit}>
            <Pencil aria-hidden />
          </Button>
          {coupon.status === "live" || coupon.status === "exhausted" ? (
            <Button variant="ghost" size="sm" onClick={() => setConfirming("end")}>
              Kết thúc
            </Button>
          ) : null}
          {coupon.used_count === 0 ? (
            <Button
              variant="ghost"
              size="icon"
              className="size-8"
              aria-label={`Xóa ${coupon.code}`}
              onClick={() => setConfirming("delete")}
            >
              <Trash2 aria-hidden />
            </Button>
          ) : null}
        </div>
      </div>
      {confirming ? (
        <div className="flex flex-wrap items-center gap-2 rounded-md bg-destructive-soft p-2 text-body-sm text-destructive-text">
          <span className="min-w-0 flex-1">
            {confirming === "end"
              ? `Kết thúc ${coupon.code} ngay bây giờ? Giỏ hàng đang áp mã sẽ không thanh toán được với mã này nữa.`
              : `Xóa hẳn ${coupon.code}? Mã chưa được dùng lần nào.`}
          </span>
          <Button
            size="sm"
            variant="destructive"
            disabled={end.isPending || remove.isPending}
            onClick={() => (confirming === "end" ? end.mutate() : remove.mutate())}
          >
            {end.isPending || remove.isPending ? <Loader2 className="animate-spin" aria-hidden /> : null}
            {confirming === "end" ? "Kết thúc" : "Xóa"}
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setConfirming(null)}>
            Hủy
          </Button>
        </div>
      ) : null}
      {error ? <p className="text-body-sm text-destructive-text">{apiErrorMessage(error)}</p> : null}
    </div>
  );
}

/** Uses so far, with a bar when there is a ceiling to fill. */
function Uses({ coupon }: { coupon: AdminCoupon }) {
  if (coupon.max_uses === null) {
    return (
      <p className="text-caption text-muted-foreground">
        {coupon.used_count} lượt đã dùng · không giới hạn
      </p>
    );
  }
  const share = coupon.max_uses === 0 ? 1 : Math.min(1, coupon.used_count / coupon.max_uses);
  return (
    <div className="flex max-w-xs items-center gap-2 pt-0.5">
      <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted" aria-hidden>
        <span
          className={cn(
            "block h-full rounded-full",
            coupon.status === "exhausted" ? "bg-warning" : "bg-primary",
          )}
          style={{ width: `${Math.max(share * 100, coupon.used_count > 0 ? 4 : 0)}%` }}
        />
      </span>
      <span className="text-caption text-muted-foreground tabular-nums">
        {coupon.used_count} / {coupon.max_uses} lượt
      </span>
    </div>
  );
}

// --- The form --------------------------------------------------------------

/** An ISO instant as the value of a `datetime-local` input, in the browser's zone. */
function toLocalInput(iso: string | null): string {
  if (!iso) return "";
  const date = new Date(iso);
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function fromLocalInput(value: string): string | null {
  return value ? new Date(value).toISOString() : null;
}

function CouponForm({ coupon, onDone }: { coupon: AdminCoupon | null; onDone: () => void }) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const typeId = useId();
  const scopeId = useId();

  const [code, setCode] = useState(coupon?.code ?? "");
  const [kind, setKind] = useState<"percent" | "fixed">(coupon?.discount_type ?? "percent");
  const [value, setValue] = useState(coupon ? String(Number(coupon.value)) : "");
  const [scope, setScope] = useState<"site" | "courses">(coupon?.scope ?? "site");
  const [courses, setCourses] = useState(coupon?.courses ?? []);
  const [maxUses, setMaxUses] = useState(coupon?.max_uses ? String(coupon.max_uses) : "");
  const [validFrom, setValidFrom] = useState(toLocalInput(coupon?.valid_from ?? null));
  const [validTo, setValidTo] = useState(toLocalInput(coupon?.valid_to ?? null));

  const save = useMutation({
    mutationFn: () => {
      const body: CouponInput = {
        discount_type: kind,
        value,
        scope,
        course_ids: scope === "courses" ? courses.map((course) => course.id) : [],
        max_uses: maxUses ? Number(maxUses) : null,
        valid_from: fromLocalInput(validFrom),
        valid_to: fromLocalInput(validTo),
      };
      return coupon
        ? updateCoupon(accessToken as string, coupon.id, body)
        : createCoupon(accessToken as string, { ...body, code });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: COUPONS_KEY });
      onDone();
    },
  });

  const valueNumber = Number(value);
  const invalid =
    (!coupon && code.trim().length < 3) ||
    !value ||
    Number.isNaN(valueNumber) ||
    valueNumber <= 0 ||
    (kind === "percent" && valueNumber > 100) ||
    (scope === "courses" && courses.length === 0);

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!invalid) save.mutate();
  }

  return (
    <form onSubmit={submit} className="grid gap-4">
      <DialogHeader>
        <DialogTitle>{coupon ? `Sửa mã ${coupon.code}` : "Tạo mã giảm giá"}</DialogTitle>
        <DialogDescription>
          {coupon
            ? "Mã không đổi được. Đơn đã đặt giữ nguyên số tiền cũ."
            : "Mã lưu ở dạng chữ in hoa; học viên gõ thường hay hoa đều được."}
        </DialogDescription>
      </DialogHeader>

      {coupon ? null : (
        <FormField
          label="Mã"
          type="text"
          value={code}
          onChange={(next) => setCode(next.toUpperCase())}
          placeholder="VD: TET2027"
          hint="3–32 ký tự: chữ không dấu, số, gạch ngang, gạch dưới."
          autoFocus
        />
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor={typeId}>Kiểu giảm</Label>
          <NativeSelect id={typeId} value={kind} onChange={(event) => setKind(event.target.value as "percent" | "fixed")}>
            <option value="percent">Theo phần trăm</option>
            <option value="fixed">Số tiền cố định (₫)</option>
          </NativeSelect>
        </div>
        <FormField
          label={kind === "percent" ? "Mức giảm (%)" : "Mức giảm (₫)"}
          type="number"
          value={value}
          onChange={setValue}
          error={kind === "percent" && valueNumber > 100 ? "Tối đa 100%" : null}
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor={scopeId}>Áp dụng cho</Label>
        <NativeSelect id={scopeId} value={scope} onChange={(event) => setScope(event.target.value as "site" | "courses")}>
          <option value="site">Toàn sàn — mọi khóa học trong giỏ</option>
          <option value="courses">Chỉ một số khóa học</option>
        </NativeSelect>
        {scope === "courses" ? <CoursePicker chosen={courses} onChange={setCourses} /> : null}
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <FormField
          label="Giới hạn lượt dùng"
          type="number"
          value={maxUses}
          onChange={setMaxUses}
          placeholder="Không giới hạn"
          hint={coupon ? `Đã dùng ${coupon.used_count} lượt` : undefined}
        />
        <FormField label="Bắt đầu" type="datetime-local" value={validFrom} onChange={setValidFrom} hint={coupon ? undefined : "Trống: ngay bây giờ"} />
        <FormField label="Kết thúc" type="datetime-local" value={validTo} onChange={setValidTo} hint="Trống: không hạn" />
      </div>

      {save.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(save.error)}</AlertDescription>
        </Alert>
      ) : null}

      <DialogFooter>
        <Button type="button" variant="ghost" onClick={onDone}>
          Hủy
        </Button>
        <Button type="submit" disabled={invalid || save.isPending}>
          {save.isPending ? <Loader2 className="animate-spin" aria-hidden /> : null}
          {coupon ? "Lưu thay đổi" : "Tạo mã"}
        </Button>
      </DialogFooter>
    </form>
  );
}

function CoursePicker({
  chosen,
  onChange,
}: {
  chosen: { id: string; title: string }[];
  onChange: (next: { id: string; title: string }[]) => void;
}) {
  const { accessToken } = useAuth();
  const [q, setQ] = useState("");
  const [asked, setAsked] = useState("");

  const results = useQuery({
    queryKey: [...ADMIN_KEY, "coupon-course-search", asked],
    queryFn: () => listAdminCourses(accessToken as string, { status: "published", q: asked, page: 1 }),
    enabled: accessToken !== null && asked.length > 0,
  });

  const chosenIds = new Set(chosen.map((course) => course.id));

  return (
    <div className="space-y-2 rounded-md border p-3">
      {chosen.length > 0 ? (
        <ul className="flex flex-wrap gap-1.5">
          {chosen.map((course) => (
            <li key={course.id}>
              <span className="inline-flex max-w-full items-center gap-1 rounded-full bg-muted py-0.5 pr-1 pl-2.5 text-xs">
                <span className="truncate">{course.title}</span>
                <button
                  type="button"
                  className="rounded-full p-0.5 transition-colors hover:bg-background"
                  aria-label={`Bỏ ${course.title}`}
                  onClick={() => onChange(chosen.filter((c) => c.id !== course.id))}
                >
                  <X className="size-3" aria-hidden />
                </button>
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-xs text-muted-foreground">Chưa chọn khóa học nào.</p>
      )}
      <div className="flex gap-2">
        <label htmlFor="coupon-course-q" className="sr-only">
          Tìm khóa học đang bán
        </label>
        <Input
          id="coupon-course-q"
          value={q}
          onChange={(event) => setQ(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              setAsked(q.trim());
            }
          }}
          placeholder="Tìm khóa học đang bán theo tên"
          className="h-8"
        />
        <Button type="button" variant="outline" size="sm" onClick={() => setAsked(q.trim())}>
          Tìm
        </Button>
      </div>
      {results.isFetching ? <p className="text-xs text-muted-foreground">Đang tìm…</p> : null}
      {results.data ? (
        results.data.items.length === 0 ? (
          <p className="text-xs text-muted-foreground">Không có khóa học đang bán nào khớp.</p>
        ) : (
          <ul className="max-h-40 space-y-1 overflow-y-auto">
            {results.data.items.map((course) => (
              <li key={course.id}>
                <button
                  type="button"
                  disabled={chosenIds.has(course.id)}
                  onClick={() => onChange([...chosen, { id: course.id, title: course.title }])}
                  className={cn(
                    "flex w-full items-center gap-2 rounded-md px-2 py-1 text-left text-sm transition-colors hover:bg-muted disabled:opacity-50",
                  )}
                >
                  <Plus className="size-3.5 shrink-0" aria-hidden />
                  <span className="min-w-0 flex-1 truncate">{course.title}</span>
                  <span className="shrink-0 text-xs text-muted-foreground">
                    {course.instructor.full_name}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )
      ) : null}
    </div>
  );
}
