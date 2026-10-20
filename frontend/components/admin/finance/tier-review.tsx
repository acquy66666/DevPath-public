"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Award, ChevronDown, Loader2, Pencil } from "lucide-react";
import { useState, type FormEvent } from "react";

import { ADMIN_KEY } from "@/components/admin/admin-nav";
import { EmptyState, ListSkeleton } from "@/components/admin/admin-shared";
import { formatCount, formatRate, formatRating } from "@/components/instructor/stats/format";
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
import { ExportButton } from "@/components/ui/export-button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { Textarea } from "@/components/ui/textarea";
import { apiErrorMessage } from "@/lib/api/error-messages";
import {
  listEvaluations,
  listTiers,
  setInstructorTier,
  tierHistory,
  TIER_REVIEW_EXPORT,
  updateTier,
  type Evaluation,
  type TierAdmin,
  type TierFlag,
  type TierUpdate,
} from "@/lib/api/finance";
import { useAuth } from "@/lib/auth/auth-provider";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";

import { money } from "./finance-shared";

const TIERS_KEY = [...ADMIN_KEY, "tiers"] as const;

const FLAGS: Record<TierFlag, { label: string; tone: string }> = {
  eligible: { label: "Đủ điều kiện lên cấp", tone: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300" },
  below_maintenance: { label: "Dưới ngưỡng duy trì", tone: "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-300" },
  recently_changed: { label: "Vừa đổi cấp < 6 tháng", tone: "bg-muted text-muted-foreground" },
  top_tier_skips_a_step: { label: "Đề xuất vượt cấp lên cao nhất", tone: "bg-muted text-muted-foreground" },
};

type Filter = "all" | "eligible" | "below_maintenance";

/**
 * Who could move up, who is slipping, and the ladder itself.
 *
 * The system only suggests: the highest tier whose every criterion the
 * numbers meet. An admin decides, with a reason the instructor will read, and
 * the decision is stored with the numbers it was made on. Sales already made
 * keep the rate they were made at.
 */
export function TierReview() {
  const { accessToken } = useAuth();
  const [filter, setFilter] = useState<Filter>("all");
  const [deciding, setDeciding] = useState<Evaluation | null>(null);
  const [editing, setEditing] = useState<TierAdmin | null>(null);

  const tiers = useQuery({
    queryKey: [...TIERS_KEY, "ladder"],
    queryFn: () => listTiers(accessToken as string),
    enabled: accessToken !== null,
  });
  const evaluations = useQuery({
    queryKey: [...TIERS_KEY, "evaluations"],
    queryFn: () => listEvaluations(accessToken as string),
    enabled: accessToken !== null,
  });

  const rows = (evaluations.data ?? []).filter((row) =>
    filter === "all" ? true : row.flags.includes(filter),
  );

  return (
    <section className="space-y-6" aria-labelledby="tiers-title">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 id="tiers-title" className="font-semibold">
            Cấp giảng viên
          </h2>
          <p className="text-sm text-muted-foreground">
            Hệ thống đề xuất cấp cao nhất mà mọi tiêu chí đều đạt; quản trị viên quyết định. Tỉ lệ
            mới áp dụng cho đơn thanh toán từ lúc đổi.
          </p>
        </div>
        <ExportButton path={TIER_REVIEW_EXPORT} filename="devpath_xet-cap-giang-vien.xlsx" />
      </div>

      {tiers.data ? (
        <ol className="grid gap-2 sm:grid-cols-5" aria-label="Bậc thang">
          {tiers.data.map((tier) => (
            <li key={tier.id} className="rounded-xl border p-3 text-sm">
              <div className="flex items-start justify-between gap-1">
                <span>
                  <span className="text-xs text-muted-foreground">Cấp {tier.rank}</span>
                  <span className="block font-semibold">{tier.name}</span>
                </span>
                <Button
                  variant="ghost"
                  size="icon"
                  className="size-7"
                  onClick={() => setEditing(tier)}
                  aria-label={`Sửa cấp ${tier.name}`}
                >
                  <Pencil className="size-3.5" aria-hidden />
                </Button>
              </div>
              <span className="block tabular-nums">{formatRate(Number(tier.share_rate))}</span>
              <span className="text-xs text-muted-foreground">
                {formatCount(tier.instructors)} giảng viên
              </span>
            </li>
          ))}
        </ol>
      ) : null}

      <div role="group" aria-label="Lọc" className="flex flex-wrap gap-1">
        {(
          [
            ["all", "Tất cả"],
            ["eligible", "Đủ điều kiện lên cấp"],
            ["below_maintenance", "Dưới ngưỡng duy trì"],
          ] as [Filter, string][]
        ).map(([value, label]) => (
          <button
            key={value}
            type="button"
            aria-pressed={value === filter}
            onClick={() => setFilter(value)}
            className={cn(
              "rounded-md border px-3 py-1.5 text-sm transition-colors",
              value === filter
                ? "border-primary bg-primary text-primary-foreground"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {label}
            {evaluations.data && value !== "all"
              ? ` (${evaluations.data.filter((row) => row.flags.includes(value)).length})`
              : ""}
          </button>
        ))}
      </div>

      {evaluations.isPending ? (
        <ListSkeleton rows={3} />
      ) : evaluations.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(evaluations.error)}</AlertDescription>
        </Alert>
      ) : rows.length === 0 ? (
        <EmptyState icon={Award} title="Không có giảng viên nào ở đây" hint="Thử bộ lọc khác." />
      ) : (
        <ul className="space-y-3">
          {rows.map((row) => (
            <EvaluationRow key={row.instructor.id} row={row} onDecide={() => setDeciding(row)} />
          ))}
        </ul>
      )}

      <DecisionDialog
        row={deciding}
        tiers={tiers.data ?? []}
        onClose={() => setDeciding(null)}
      />
      <TierEditDialog
        tier={editing}
        onClose={() => setEditing(null)}
      />
    </section>
  );
}

function EvaluationRow({ row, onDecide }: { row: Evaluation; onDecide: () => void }) {
  const { accessToken } = useAuth();
  const [open, setOpen] = useState(false);
  const m = row.metrics;
  const nextCheck = row.checks.find((check) => check.tier.rank === row.current.rank + 1);

  const history = useQuery({
    queryKey: [...TIERS_KEY, "history", row.instructor.id],
    queryFn: () => tierHistory(accessToken as string, row.instructor.id),
    enabled: open && accessToken !== null,
  });

  return (
    <li className="rounded-xl border">
      <div className="flex flex-wrap items-start justify-between gap-3 p-4">
        <div className="min-w-0">
          <p className="font-medium">{row.instructor.full_name}</p>
          <p className="truncate text-xs text-muted-foreground">{row.instructor.email}</p>
          <p className="mt-2 flex flex-wrap items-center gap-2 text-sm">
            <Badge variant="outline">
              {row.current.name} · {formatRate(Number(row.current.share_rate))}
            </Badge>
            {row.suggested.rank !== row.current.rank ? (
              <span className="text-muted-foreground">
                → đề xuất <strong className="text-foreground">{row.suggested.name}</strong>
              </span>
            ) : null}
            {row.flags.map((flag) => (
              <span key={flag} className={cn("rounded-full px-2 py-0.5 text-xs", FLAGS[flag].tone)}>
                {FLAGS[flag].label}
              </span>
            ))}
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="ghost" size="sm" onClick={() => setOpen((value) => !value)} aria-expanded={open}>
            <ChevronDown className={cn("transition-transform", open && "rotate-180")} aria-hidden />
            Chi tiết
          </Button>
          <Button size="sm" onClick={onDecide}>
            Đổi cấp
          </Button>
        </div>
      </div>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-1 border-t px-4 py-3 text-xs sm:grid-cols-4">
        <Metric label="HV trả phí" value={formatCount(m.paid_students)} />
        <Metric label="Doanh thu 12 tháng" value={money(m.revenue_12m)} />
        <Metric label="Đánh giá (Bayes)" value={`${formatRating(m.rating)} · ${formatCount(m.reviews)}`} />
        <Metric label="Hoàn thành" value={formatRate(m.completion_rate)} />
        <Metric
          label="Trả lời Q&A 48 giờ"
          value={m.qa_questions < 5 ? `${m.qa_questions} câu` : formatRate(m.qa_answer_rate)}
        />
        <Metric label="Khóa đang bán" value={formatCount(m.published_courses)} />
        <Metric label="Tháng hoạt động" value={formatCount(m.months_active)} />
        <Metric
          label="Khóa bị gỡ (90 ngày)"
          value={formatCount(m.removed_courses_90d)}
          warn={m.removed_courses_90d > 0 || m.locked}
        />
      </dl>
      {open ? (
        <div className="space-y-4 border-t p-4">
          {nextCheck ? (
            <div>
              <p className="mb-2 text-sm font-medium">Tiêu chí lên “{nextCheck.tier.name}”</p>
              <ul className="space-y-1 text-sm">
                {nextCheck.criteria.map((criterion) => (
                  <li key={criterion.key} className="flex flex-wrap justify-between gap-2">
                    <span className={criterion.met ? "" : "text-muted-foreground"}>
                      {criterion.met ? "✓" : "○"} {criterion.label}
                      {criterion.admin_only ? (
                        <span className="ml-1 text-xs text-muted-foreground">(giảng viên chỉ thấy đạt/chưa)</span>
                      ) : null}
                    </span>
                    <span className="tabular-nums">
                      {criterion.value} <span className="text-muted-foreground">/ {criterion.threshold}</span>
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          <div>
            <p className="mb-2 text-sm font-medium">Lịch sử quyết định</p>
            {history.data && history.data.length > 0 ? (
              <ul className="space-y-2 text-sm">
                {history.data.map((change) => (
                  <li key={change.id} className="rounded-lg bg-muted/40 p-2">
                    <span className="font-medium">
                      {change.from_tier?.name ?? "Khởi hành"} → {change.to_tier.name}
                    </span>{" "}
                    <span className="text-xs text-muted-foreground">
                      {formatDate(change.created_at)}
                      {change.decided_by ? ` · ${change.decided_by.full_name}` : ""}
                    </span>
                    <p className="text-muted-foreground">{change.note}</p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">
                {history.isPending ? "Đang tải…" : "Chưa có quyết định nào."}
              </p>
            )}
          </div>
        </div>
      ) : null}
    </li>
  );
}

function Metric({ label, value, warn }: { label: string; value: string; warn?: boolean }) {
  return (
    <div className="flex justify-between gap-2">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className={cn("tabular-nums", warn && "font-medium text-red-700 dark:text-red-400")}>{value}</dd>
    </div>
  );
}

function DecisionDialog({
  row,
  tiers,
  onClose,
}: {
  row: Evaluation | null;
  tiers: TierAdmin[];
  onClose: () => void;
}) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const [tierId, setTierId] = useState("");
  const [note, setNote] = useState("");
  const [lastRow, setLastRow] = useState<Evaluation | null>(null);

  if (row !== lastRow) {
    // A different instructor: start from the suggestion, or the next step up.
    setLastRow(row);
    if (row) {
      const fallback = tiers.find((tier) => tier.rank === row.current.rank + 1) ?? tiers[0];
      setTierId(row.suggested.id !== row.current.id ? row.suggested.id : (fallback?.id ?? ""));
      setNote("");
    }
  }

  const decide = useMutation({
    mutationFn: () =>
      setInstructorTier(accessToken as string, row!.instructor.id, { tier_id: tierId, note }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: TIERS_KEY });
      onClose();
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    decide.mutate();
  }

  return (
    <Dialog open={row !== null} onOpenChange={(open) => (open ? null : onClose())}>
      <DialogContent>
        <form onSubmit={submit} className="space-y-4">
          <DialogHeader>
            <DialogTitle>Đổi cấp cho {row?.instructor.full_name}</DialogTitle>
            <DialogDescription>
              Đang ở “{row?.current.name}”. Giảng viên nhận thông báo kèm lý do; các lượt bán đã có
              giữ nguyên tỉ lệ cũ.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="tier-target">Cấp mới</Label>
            <NativeSelect id="tier-target" value={tierId} onChange={(event) => setTierId(event.target.value)}>
              {tiers.map((tier) => (
                <option key={tier.id} value={tier.id} disabled={tier.id === row?.current.id}>
                  {tier.rank}. {tier.name} — {formatRate(Number(tier.share_rate))}
                  {tier.id === row?.suggested.id ? " (đề xuất)" : ""}
                </option>
              ))}
            </NativeSelect>
          </div>
          <div className="space-y-2">
            <Label htmlFor="tier-note">Lý do (giảng viên sẽ đọc)</Label>
            <Textarea
              id="tier-note"
              value={note}
              onChange={(event) => setNote(event.target.value)}
              rows={4}
              maxLength={1000}
              required
              placeholder="Ví dụ: Đạt mọi tiêu chí cấp Dẫn đường, phản hồi Hỏi đáp rất nhanh."
            />
          </div>
          {decide.isError ? (
            <Alert variant="destructive">
              <AlertDescription>{apiErrorMessage(decide.error)}</AlertDescription>
            </Alert>
          ) : null}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Hủy
            </Button>
            <Button type="submit" disabled={decide.isPending || !note.trim() || !tierId}>
              {decide.isPending ? <Loader2 className="animate-spin" aria-hidden /> : null}
              Xác nhận đổi cấp
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

const PERCENT_FIELDS = new Set(["share_rate", "min_completion_rate", "min_qa_answer_rate"]);

const FIELDS: { key: keyof TierUpdate; label: string; optional?: boolean; hint?: string }[] = [
  { key: "share_rate", label: "Giảng viên nhận (%)" },
  { key: "min_paid_students", label: "Học viên trả phí tối thiểu" },
  { key: "min_revenue_12m", label: "Doanh thu 12 tháng tối thiểu (₫)" },
  { key: "min_rating", label: "Điểm đánh giá tối thiểu (1–5)", optional: true },
  { key: "min_reviews", label: "Số đánh giá tối thiểu" },
  { key: "min_completion_rate", label: "Tỉ lệ hoàn thành tối thiểu (%)", optional: true },
  { key: "min_qa_answer_rate", label: "Trả lời Hỏi đáp trong 48 giờ (%)", optional: true },
  { key: "min_published_courses", label: "Khóa đang bán tối thiểu" },
  { key: "min_months_active", label: "Số tháng hoạt động tối thiểu" },
];

function toForm(tier: TierAdmin): Record<string, string> {
  const form: Record<string, string> = { name: tier.name, description: tier.description ?? "" };
  for (const field of FIELDS) {
    const raw = tier[field.key as keyof TierAdmin];
    if (raw === null || raw === undefined) form[field.key] = "";
    else if (PERCENT_FIELDS.has(field.key)) form[field.key] = String(Math.round(Number(raw) * 10000) / 100);
    else form[field.key] = String(Number(raw));
  }
  return form;
}

function TierEditDialog({ tier, onClose }: { tier: TierAdmin | null; onClose: () => void }) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const [form, setForm] = useState<Record<string, string>>({});
  const [lastTier, setLastTier] = useState<TierAdmin | null>(null);

  if (tier !== lastTier) {
    setLastTier(tier);
    if (tier) setForm(toForm(tier));
  }

  const save = useMutation({
    mutationFn: () => {
      const body: Record<string, string | number | null> = {
        name: form.name,
        description: form.description || null,
      };
      for (const field of FIELDS) {
        const value = form[field.key]?.trim() ?? "";
        if (value === "") {
          if (field.optional) body[field.key] = null;
          continue;
        }
        body[field.key] = PERCENT_FIELDS.has(field.key)
          ? (Number(value) / 100).toFixed(4)
          : field.key === "min_rating" || field.key === "min_revenue_12m"
            ? value
            : Number(value);
      }
      return updateTier(accessToken as string, tier!.id, body as TierUpdate);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: TIERS_KEY });
      onClose();
    },
  });

  return (
    <Dialog open={tier !== null} onOpenChange={(open) => (open ? null : onClose())}>
      <DialogContent className="max-h-[85vh] overflow-y-auto">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            save.mutate();
          }}
          className="space-y-4"
        >
          <DialogHeader>
            <DialogTitle>Sửa cấp {tier?.rank}</DialogTitle>
            <DialogDescription>
              Tỉ lệ mới chỉ áp dụng cho lượt bán từ bây giờ. Để trống một tiêu chí không bắt buộc là
              bỏ xét tiêu chí đó.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="tier-name">Tên cấp</Label>
            <Input
              id="tier-name"
              value={form.name ?? ""}
              onChange={(event) => setForm({ ...form, name: event.target.value })}
              maxLength={50}
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="tier-description">Mô tả</Label>
            <Textarea
              id="tier-description"
              value={form.description ?? ""}
              onChange={(event) => setForm({ ...form, description: event.target.value })}
              rows={2}
              maxLength={500}
            />
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {FIELDS.map((field) => (
              <div key={field.key} className="space-y-1">
                <Label htmlFor={`tier-${field.key}`} className="text-xs">
                  {field.label}
                </Label>
                <Input
                  id={`tier-${field.key}`}
                  inputMode="decimal"
                  value={form[field.key] ?? ""}
                  onChange={(event) => setForm({ ...form, [field.key]: event.target.value })}
                  placeholder={field.optional ? "Không xét" : undefined}
                  required={!field.optional}
                />
              </div>
            ))}
          </div>
          {save.isError ? (
            <Alert variant="destructive">
              <AlertDescription>{apiErrorMessage(save.error)}</AlertDescription>
            </Alert>
          ) : null}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Hủy
            </Button>
            <Button type="submit" disabled={save.isPending}>
              {save.isPending ? <Loader2 className="animate-spin" aria-hidden /> : null}
              Lưu
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
