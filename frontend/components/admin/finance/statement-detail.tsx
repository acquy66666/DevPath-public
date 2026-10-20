"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, CheckCheck, Loader2, Printer, Trash2, XCircle } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { ListSkeleton } from "@/components/admin/admin-shared";
import { formatCount, formatRate } from "@/components/instructor/stats/format";
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
import { Textarea } from "@/components/ui/textarea";
import { apiErrorMessage } from "@/lib/api/error-messages";
import {
  confirmStatement,
  deleteStatement,
  getStatement,
  PAYOUT_STATUS_LABELS,
  payStatement,
  setWithholding,
  statementExportPath,
  voidStatement,
  type StatementDetail as Detail,
} from "@/lib/api/finance";
import { useAuth } from "@/lib/auth/auth-provider";
import { formatDate } from "@/lib/format";

import { day, money } from "./finance-shared";
import { PAYOUTS_KEY, STATUS_VARIANT } from "./payouts-page";

const DATE_TIME = new Intl.DateTimeFormat("vi-VN", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "Asia/Ho_Chi_Minh",
});

/**
 * One payout statement -- the "check bill" handed to an instructor.
 *
 * Laid out to print: the actions sit above it and disappear on paper. A draft
 * can have its tax withholding switched and be thrown away; confirming locks
 * the figures; paying records the bank transfer; voiding (never once paid)
 * sends its sales back to be billed again.
 */
export function StatementDetail({ id }: { id: string }) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const router = useRouter();
  const [paying, setPaying] = useState(false);
  const [voiding, setVoiding] = useState(false);

  const query = useQuery({
    queryKey: [...PAYOUTS_KEY, "statement", id],
    queryFn: () => getStatement(accessToken as string, id),
    enabled: accessToken !== null,
  });

  async function refresh(next?: Detail) {
    if (next) queryClient.setQueryData([...PAYOUTS_KEY, "statement", id], next);
    await queryClient.invalidateQueries({ queryKey: PAYOUTS_KEY });
  }

  const confirm = useMutation({
    mutationFn: () => confirmStatement(accessToken as string, id),
    onSuccess: refresh,
  });
  const withhold = useMutation({
    mutationFn: (value: boolean) => setWithholding(accessToken as string, id, value),
    onSuccess: refresh,
  });
  const remove = useMutation({
    mutationFn: () => deleteStatement(accessToken as string, id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: PAYOUTS_KEY });
      router.push("/quan-tri/thanh-toan");
    },
  });

  if (query.isPending) return <ListSkeleton rows={3} height="h-32" />;
  if (query.isError) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{apiErrorMessage(query.error)}</AlertDescription>
      </Alert>
    );
  }

  const s = query.data;
  const actionError = confirm.error ?? withhold.error ?? remove.error;

  return (
    <div className="space-y-6">
      <div className="space-y-3 print:hidden">
        <Link
          href="/quan-tri/thanh-toan"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-4" aria-hidden />
          Thanh toán giảng viên
        </Link>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <h2 className="font-mono text-lg font-semibold">{s.code}</h2>
            <Badge variant={STATUS_VARIANT[s.status]}>{PAYOUT_STATUS_LABELS[s.status]}</Badge>
          </div>
          <div className="flex flex-wrap gap-2">
            <ExportButton path={statementExportPath(s.id)} filename={`devpath_bang-ke_${s.code}.xlsx`} />
            <Button variant="outline" size="sm" onClick={() => window.print()}>
              <Printer aria-hidden />
              In
            </Button>
            {s.status === "draft" ? (
              <>
                <Button size="sm" onClick={() => confirm.mutate()} disabled={confirm.isPending}>
                  {confirm.isPending ? <Loader2 className="animate-spin" aria-hidden /> : <CheckCheck aria-hidden />}
                  Chốt bảng kê
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => remove.mutate()}
                  disabled={remove.isPending}
                >
                  <Trash2 aria-hidden />
                  Xóa nháp
                </Button>
              </>
            ) : null}
            {s.status === "confirmed" ? (
              <Button size="sm" onClick={() => setPaying(true)}>
                Ghi nhận đã chi
              </Button>
            ) : null}
            {s.status === "draft" || s.status === "confirmed" ? (
              <Button variant="ghost" size="sm" onClick={() => setVoiding(true)}>
                <XCircle aria-hidden />
                Hủy
              </Button>
            ) : null}
          </div>
        </div>
        {s.status === "draft" ? (
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={Number(s.tax_withheld) > 0}
              disabled={withhold.isPending || Number(s.instructor_amount) < 5_000_000}
              onChange={(event) => withhold.mutate(event.target.checked)}
            />
            Khấu trừ thuế TNCN 10% (bỏ chọn nếu giảng viên đã nộp mẫu 08/CK-TNCN)
          </label>
        ) : null}
        {actionError ? (
          <Alert variant="destructive">
            <AlertDescription>{apiErrorMessage(actionError)}</AlertDescription>
          </Alert>
        ) : null}
      </div>

      <article className="space-y-6 rounded-xl border bg-card p-6 print:border-0 print:p-0">
        <header className="flex flex-wrap items-start justify-between gap-4 border-b pb-4">
          <div>
            <p className="text-xs tracking-widest text-muted-foreground uppercase">DevPath</p>
            <h1 className="text-xl font-semibold">Bảng kê thanh toán hoa hồng giảng viên</h1>
            <p className="text-sm text-muted-foreground">
              Kỳ {day(s.period_start)} – {day(s.period_end)}
              {s.carried_lines > 0 ? ` · gồm ${formatCount(s.carried_lines)} dòng tồn từ kỳ trước` : ""}
            </p>
          </div>
          <dl className="text-right text-sm">
            <dt className="text-xs text-muted-foreground">Mã bảng kê</dt>
            <dd className="font-mono font-semibold">{s.code}</dd>
            <dt className="mt-1 text-xs text-muted-foreground">Trạng thái</dt>
            <dd>{PAYOUT_STATUS_LABELS[s.status]}</dd>
          </dl>
        </header>

        <section className="grid gap-4 sm:grid-cols-2">
          <dl className="space-y-1 text-sm">
            <dt className="text-xs text-muted-foreground">Giảng viên</dt>
            <dd className="font-medium">{s.instructor_name}</dd>
            <dd className="text-muted-foreground">{s.instructor_email}</dd>
          </dl>
          <dl className="space-y-1 text-sm sm:text-right">
            <dt className="text-xs text-muted-foreground">Lập lúc</dt>
            <dd>{DATE_TIME.format(new Date(s.created_at))}</dd>
            {s.confirmed_at ? <dd className="text-muted-foreground">Chốt {DATE_TIME.format(new Date(s.confirmed_at))}</dd> : null}
            {s.paid_at ? (
              <dd className="text-muted-foreground">
                Chi {DATE_TIME.format(new Date(s.paid_at))} · mã chuyển khoản{" "}
                <span className="font-mono">{s.payment_reference}</span>
              </dd>
            ) : null}
          </dl>
        </section>

        <table className="w-full text-sm">
          <tbody>
            <SummaryRow label="Học viên đã trả cho các khóa học" value={s.gross_amount} />
            <SummaryRow label="Phần sàn giữ" value={s.platform_amount} muted />
            <SummaryRow label="Hoa hồng giảng viên" value={s.instructor_amount} strong />
            <SummaryRow label="Thuế TNCN khấu trừ (ước tính)" value={`-${s.tax_withheld}`} muted />
            <SummaryRow label="Số tiền thực chi" value={s.payable_amount} strong big />
          </tbody>
        </table>

        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-sm">
            <thead>
              <tr className="border-b text-left text-xs text-muted-foreground">
                <th className="py-2 pr-3 font-medium">Mã đơn</th>
                <th className="px-3 py-2 font-medium">Thanh toán</th>
                <th className="px-3 py-2 font-medium">Khóa học</th>
                <th className="px-3 py-2 text-right font-medium">Học viên trả</th>
                <th className="px-3 py-2 text-right font-medium">Tỉ lệ</th>
                <th className="py-2 pl-3 text-right font-medium">Hoa hồng</th>
              </tr>
            </thead>
            <tbody>
              {s.lines.map((line) => (
                <tr key={line.id} className="border-b last:border-0">
                  <td className="py-1.5 pr-3 font-mono text-xs">{line.order_code}</td>
                  <td className="px-3 py-1.5 tabular-nums">{formatDate(line.paid_at)}</td>
                  <td className="px-3 py-1.5">
                    {line.course_title}
                    {Number(line.discount) > 0 ? (
                      <span className="block text-xs text-muted-foreground">
                        Giá {money(line.unit_price)}, giảm {money(line.discount)}
                      </span>
                    ) : null}
                  </td>
                  <td className="px-3 py-1.5 text-right tabular-nums">{money(line.net_amount)}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums">{formatRate(Number(line.share_rate))}</td>
                  <td className="py-1.5 pl-3 text-right tabular-nums">{money(line.instructor_amount)}</td>
                </tr>
              ))}
              {s.lines.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-4 text-center text-muted-foreground">
                    {s.status === "void"
                      ? "Bảng kê đã hủy — các dòng bán đã được trả lại để lập bảng kê khác."
                      : "Không có dòng nào."}
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>

        {s.void_reason ? (
          <p className="text-sm text-destructive">Lý do hủy: {s.void_reason}</p>
        ) : null}
        {s.note ? <p className="text-sm text-muted-foreground">Ghi chú: {s.note}</p> : null}

        <footer className="space-y-6 border-t pt-4 text-xs text-muted-foreground">
          <p>
            Hoa hồng = làm tròn xuống tới đồng của (số tiền học viên trả × tỉ lệ chia theo cấp giảng
            viên tại thời điểm bán). Thuế TNCN là ước tính 10% khi một lần chi từ 5.000.000 ₫ (NĐ
            253/2026), cần kế toán xác nhận.
          </p>
          <div className="grid grid-cols-2 gap-8 text-center">
            <div>
              <p className="font-medium text-foreground">Người lập</p>
              <p className="mt-12">(Ký, ghi rõ họ tên)</p>
            </div>
            <div>
              <p className="font-medium text-foreground">Giảng viên xác nhận</p>
              <p className="mt-12">(Ký, ghi rõ họ tên)</p>
            </div>
          </div>
        </footer>
      </article>

      <PayDialog open={paying} onClose={() => setPaying(false)} id={s.id} onDone={refresh} />
      <VoidDialog open={voiding} onClose={() => setVoiding(false)} id={s.id} onDone={refresh} />
    </div>
  );
}

function SummaryRow({
  label,
  value,
  strong,
  muted,
  big,
}: {
  label: string;
  value: string;
  strong?: boolean;
  muted?: boolean;
  big?: boolean;
}) {
  const negative = value.startsWith("-");
  const amount = money(negative ? value.slice(1) : value);
  return (
    <tr className="border-b last:border-0">
      <th scope="row" className={`py-2 text-left font-normal ${muted ? "text-muted-foreground" : ""}`}>
        {label}
      </th>
      <td
        className={`py-2 text-right tabular-nums ${strong ? "font-semibold" : ""} ${big ? "text-lg" : ""} ${muted ? "text-muted-foreground" : ""}`}
      >
        {negative && amount !== "0 ₫" ? `− ${amount}` : amount}
      </td>
    </tr>
  );
}

function PayDialog({
  open,
  onClose,
  id,
  onDone,
}: {
  open: boolean;
  onClose: () => void;
  id: string;
  onDone: (detail: Detail) => Promise<void>;
}) {
  const { accessToken } = useAuth();
  const [reference, setReference] = useState("");
  const pay = useMutation({
    mutationFn: () => payStatement(accessToken as string, id, reference),
    onSuccess: async (detail) => {
      await onDone(detail);
      onClose();
    },
  });
  return (
    <Dialog open={open} onOpenChange={(value) => (value ? null : onClose())}>
      <DialogContent>
        <form
          className="space-y-4"
          onSubmit={(event) => {
            event.preventDefault();
            pay.mutate();
          }}
        >
          <DialogHeader>
            <DialogTitle>Ghi nhận đã chi</DialogTitle>
            <DialogDescription>
              Sau bước này bảng kê là bản ghi cuối cùng, không hủy được nữa.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="pay-reference">Mã giao dịch chuyển khoản</Label>
            <Input
              id="pay-reference"
              value={reference}
              onChange={(event) => setReference(event.target.value)}
              maxLength={100}
              required
              placeholder="Ví dụ: FT26103999123"
            />
          </div>
          {pay.isError ? (
            <Alert variant="destructive">
              <AlertDescription>{apiErrorMessage(pay.error)}</AlertDescription>
            </Alert>
          ) : null}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Để sau
            </Button>
            <Button type="submit" disabled={pay.isPending || !reference.trim()}>
              {pay.isPending ? <Loader2 className="animate-spin" aria-hidden /> : null}
              Xác nhận đã chi
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function VoidDialog({
  open,
  onClose,
  id,
  onDone,
}: {
  open: boolean;
  onClose: () => void;
  id: string;
  onDone: (detail: Detail) => Promise<void>;
}) {
  const { accessToken } = useAuth();
  const [reason, setReason] = useState("");
  const cancel = useMutation({
    mutationFn: () => voidStatement(accessToken as string, id, reason),
    onSuccess: async (detail) => {
      await onDone(detail);
      onClose();
    },
  });
  return (
    <Dialog open={open} onOpenChange={(value) => (value ? null : onClose())}>
      <DialogContent>
        <form
          className="space-y-4"
          onSubmit={(event) => {
            event.preventDefault();
            cancel.mutate();
          }}
        >
          <DialogHeader>
            <DialogTitle>Hủy bảng kê</DialogTitle>
            <DialogDescription>
              Các dòng bán sẽ được trả lại để lập bảng kê khác. Phần đầu bảng kê và lý do được giữ
              lại.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="void-reason">Lý do</Label>
            <Textarea
              id="void-reason"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              rows={3}
              maxLength={1000}
              required
            />
          </div>
          {cancel.isError ? (
            <Alert variant="destructive">
              <AlertDescription>{apiErrorMessage(cancel.error)}</AlertDescription>
            </Alert>
          ) : null}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Không hủy
            </Button>
            <Button type="submit" variant="destructive" disabled={cancel.isPending || !reason.trim()}>
              {cancel.isPending ? <Loader2 className="animate-spin" aria-hidden /> : null}
              Hủy bảng kê
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
