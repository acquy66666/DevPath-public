"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, Loader2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { ADMIN_KEY } from "@/components/admin/admin-nav";
import { EmptyState, ListSkeleton } from "@/components/admin/admin-shared";
import { formatCount, formatRate } from "@/components/instructor/stats/format";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ExportButton } from "@/components/ui/export-button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { Pager } from "@/components/ui/pager";
import { apiErrorMessage } from "@/lib/api/error-messages";
import {
  createStatements,
  getBalances,
  listStatements,
  PAYOUT_STATUS_LABELS,
  payoutsExportPath,
  type PayoutStatus,
  type StatementBatch,
} from "@/lib/api/finance";
import { useAuth } from "@/lib/auth/auth-provider";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";

import { MoneyCell, money, vietnamToday } from "./finance-shared";

export const PAYOUTS_KEY = [...ADMIN_KEY, "payouts"] as const;

export const STATUS_VARIANT: Record<PayoutStatus, "default" | "secondary" | "outline" | "destructive"> = {
  draft: "outline",
  confirmed: "secondary",
  paid: "default",
  void: "destructive",
};

function lastMonth(today: string): string {
  const [y, m] = today.split("-").map(Number);
  const index = y * 12 + m - 2;
  return `${Math.floor(index / 12)}-${String((index % 12) + 1).padStart(2, "0")}`;
}

/**
 * What each instructor is owed, and the statements that pay it.
 *
 * A statement is drawn up for a month that is over: every paid sale up to its
 * end that is on no statement yet, earlier months carried in. Under the
 * minimum waits for the next month, except in December.
 */
export function PayoutsPage() {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const [month, setMonth] = useState(lastMonth(vietnamToday()));
  const [status, setStatus] = useState<PayoutStatus | "">("");
  const [page, setPage] = useState(1);
  const [batch, setBatch] = useState<StatementBatch | null>(null);

  const balances = useQuery({
    queryKey: [...PAYOUTS_KEY, "balances"],
    queryFn: () => getBalances(accessToken as string),
    enabled: accessToken !== null,
  });
  const statements = useQuery({
    queryKey: [...PAYOUTS_KEY, "statements", status, page],
    queryFn: () => listStatements(accessToken as string, { status, page }),
    enabled: accessToken !== null,
    placeholderData: keepPreviousData,
  });

  const create = useMutation({
    mutationFn: () => createStatements(accessToken as string, `${month}-01`),
    onSuccess: async (result) => {
      setBatch(result);
      await queryClient.invalidateQueries({ queryKey: PAYOUTS_KEY });
    },
  });

  const settings = balances.data?.settings;

  return (
    <section className="space-y-6" aria-labelledby="payouts-title">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 id="payouts-title" className="font-semibold">
            Hoa hồng & thanh toán giảng viên
          </h2>
          <p className="text-sm text-muted-foreground">
            {settings
              ? `Chi tối thiểu ${money(settings.minimum)} mỗi kỳ (tháng 12 trả hết). Thuế TNCN ước tính ${formatRate(Number(settings.pit_rate))} khi một lần chi từ ${money(settings.pit_threshold)}.`
              : "Số dư, bảng kê theo tháng và lịch sử chi trả."}
          </p>
        </div>
        <ExportButton path={payoutsExportPath({ status })} filename="devpath_thanh-toan-giang-vien.xlsx" />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Lập bảng kê</CardTitle>
          <CardDescription>
            Cho một tháng đã kết thúc: mỗi giảng viên còn tiền chưa lập bảng kê nhận một bảng kê
            nháp, gồm cả các dòng tồn từ tháng trước.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <form
            className="flex flex-wrap items-end gap-3"
            onSubmit={(event) => {
              event.preventDefault();
              create.mutate();
            }}
          >
            <div className="space-y-1">
              <Label htmlFor="payout-month" className="text-xs">
                Tháng
              </Label>
              <Input
                id="payout-month"
                type="month"
                value={month}
                max={lastMonth(vietnamToday())}
                onChange={(event) => event.target.value && setMonth(event.target.value)}
                className="h-9 w-44"
              />
            </div>
            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? <Loader2 className="animate-spin" aria-hidden /> : <FileText aria-hidden />}
              Lập bảng kê
            </Button>
          </form>
          {create.isError ? (
            <Alert variant="destructive">
              <AlertDescription>{apiErrorMessage(create.error)}</AlertDescription>
            </Alert>
          ) : null}
          {batch ? (
            <Alert>
              <AlertDescription>
                Kỳ {formatDate(batch.period_start)} – {formatDate(batch.period_end)}: lập{" "}
                {formatCount(batch.created.length)} bảng kê nháp.
                {batch.skipped.length > 0
                  ? ` ${batch.skipped.length} giảng viên dưới mức chi tối thiểu được dồn sang kỳ sau: ${batch.skipped
                      .map((s) => `${s.instructor.full_name} (${money(s.amount)})`)
                      .join(", ")}.`
                  : ""}
                {batch.created.length === 0 && batch.skipped.length === 0
                  ? " Không còn dòng bán nào chưa lập bảng kê tới cuối tháng này."
                  : ""}
              </AlertDescription>
            </Alert>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Số dư từng giảng viên</CardTitle>
          <CardDescription>Hoa hồng tính trên số tiền học viên thực trả, theo tỉ lệ chốt lúc bán.</CardDescription>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          {balances.isPending ? (
            <ListSkeleton rows={2} height="h-10" />
          ) : balances.isError ? (
            <Alert variant="destructive">
              <AlertDescription>{apiErrorMessage(balances.error)}</AlertDescription>
            </Alert>
          ) : balances.data.items.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">Chưa giảng viên nào có hoa hồng.</p>
          ) : (
            <table className="w-full min-w-[820px] text-sm">
              <thead>
                <tr className="border-b text-left text-xs text-muted-foreground">
                  <th className="py-2 pr-3 font-medium">Giảng viên</th>
                  <th className="px-3 py-2 text-right font-medium">Từ trước tới nay</th>
                  <th className="px-3 py-2 text-right font-medium">Chưa lập bảng kê</th>
                  <th className="px-3 py-2 text-right font-medium">Nháp</th>
                  <th className="px-3 py-2 text-right font-medium">Đã chốt, chưa chi</th>
                  <th className="px-3 py-2 text-right font-medium">Đã chi</th>
                  <th className="py-2 pl-3 text-right font-medium">Thuế đã tính</th>
                </tr>
              </thead>
              <tbody>
                {balances.data.items.map((row) => (
                  <tr key={row.instructor.id} className="border-b last:border-0">
                    <th scope="row" className="py-2 pr-3 text-left font-normal">
                      <span className="font-medium">{row.instructor.full_name}</span>
                      <span className="block text-xs text-muted-foreground">{row.instructor.email}</span>
                    </th>
                    <MoneyCell value={row.earned_all_time} />
                    <td className="px-3 py-2 text-right tabular-nums">
                      {money(row.unbilled)}
                      {row.unbilled_lines > 0 ? (
                        <span className="block text-xs text-muted-foreground">
                          {formatCount(row.unbilled_lines)} dòng
                          {row.oldest_unbilled ? ` từ ${formatDate(row.oldest_unbilled)}` : ""}
                        </span>
                      ) : null}
                    </td>
                    <MoneyCell value={row.in_draft} muted />
                    <MoneyCell value={row.confirmed_unpaid} />
                    <MoneyCell value={row.paid_out} />
                    <td className="py-2 pl-3 text-right tabular-nums text-muted-foreground">
                      {money(row.tax_withheld)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <CardTitle>Bảng kê</CardTitle>
            <CardDescription>Bấm mã để xem chi tiết, chốt, ghi nhận đã chi hoặc in.</CardDescription>
          </div>
          <NativeSelect
            aria-label="Lọc theo trạng thái"
            value={status}
            onChange={(event) => {
              setStatus(event.target.value as PayoutStatus | "");
              setPage(1);
            }}
            className="h-9 w-44"
          >
            <option value="">Mọi trạng thái</option>
            {(Object.keys(PAYOUT_STATUS_LABELS) as PayoutStatus[]).map((value) => (
              <option key={value} value={value}>
                {PAYOUT_STATUS_LABELS[value]}
              </option>
            ))}
          </NativeSelect>
        </CardHeader>
        <CardContent className="space-y-4">
          {statements.isPending ? (
            <ListSkeleton rows={3} height="h-12" />
          ) : statements.isError ? (
            <Alert variant="destructive">
              <AlertDescription>{apiErrorMessage(statements.error)}</AlertDescription>
            </Alert>
          ) : statements.data.items.length === 0 ? (
            <EmptyState title="Chưa có bảng kê nào" hint="Chọn một tháng đã qua rồi bấm “Lập bảng kê”." />
          ) : (
            <div className={cn("overflow-x-auto transition-opacity", statements.isFetching && "opacity-60")}>
              <table className="w-full min-w-[760px] text-sm">
                <thead>
                  <tr className="border-b text-left text-xs text-muted-foreground">
                    <th className="py-2 pr-3 font-medium">Mã</th>
                    <th className="px-3 py-2 font-medium">Giảng viên</th>
                    <th className="px-3 py-2 font-medium">Kỳ</th>
                    <th className="px-3 py-2 font-medium">Trạng thái</th>
                    <th className="px-3 py-2 text-right font-medium">Dòng</th>
                    <th className="px-3 py-2 text-right font-medium">Hoa hồng</th>
                    <th className="py-2 pl-3 text-right font-medium">Thực chi</th>
                  </tr>
                </thead>
                <tbody>
                  {statements.data.items.map((row) => (
                    <tr key={row.id} className="border-b last:border-0">
                      <th scope="row" className="py-2 pr-3 text-left font-normal">
                        <Link href={`/quan-tri/thanh-toan/${row.id}`} className="font-mono font-medium hover:underline">
                          {row.code}
                        </Link>
                      </th>
                      <td className="px-3 py-2">{row.instructor_name}</td>
                      <td className="px-3 py-2 tabular-nums">{row.period_start.slice(5, 7)}/{row.period_start.slice(0, 4)}</td>
                      <td className="px-3 py-2">
                        <Badge variant={STATUS_VARIANT[row.status]}>{PAYOUT_STATUS_LABELS[row.status]}</Badge>
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums">{formatCount(row.line_count)}</td>
                      <MoneyCell value={row.instructor_amount} />
                      <td className="py-2 pl-3 text-right font-medium tabular-nums">{money(row.payable_amount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {statements.data ? (
            <Pager page={page} pageSize={statements.data.page_size} total={statements.data.total} onPage={setPage} />
          ) : null}
        </CardContent>
      </Card>
    </section>
  );
}
