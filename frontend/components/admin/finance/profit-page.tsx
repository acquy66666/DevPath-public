"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Pencil, Plus, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";

import { ADMIN_KEY } from "@/components/admin/admin-nav";
import { EmptyState, ListSkeleton } from "@/components/admin/admin-shared";
import { formatRate } from "@/components/instructor/stats/format";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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
import { Pager } from "@/components/ui/pager";
import { apiErrorMessage } from "@/lib/api/error-messages";
import {
  createExpense,
  deleteExpense,
  expensesPath,
  getProfit,
  listExpenses,
  profitPath,
  updateExpense,
  type Expense,
  type ExpenseCategory,
  type ExpenseInput,
  type ProfitColumn,
} from "@/lib/api/finance";
import { useAuth } from "@/lib/auth/auth-provider";
import { cn } from "@/lib/utils";

import { day, money, vietnamToday } from "./finance-shared";

const PROFIT_KEY = [...ADMIN_KEY, "profit"] as const;

const CATEGORY_LABELS: Record<ExpenseCategory, string> = {
  infrastructure: "Hạ tầng (máy chủ, tên miền, lưu trữ)",
  ai_api: "API AI (Gemini)",
  payment_fee: "Phí cổng thanh toán (điều chỉnh thực tế)",
  marketing: "Marketing",
  staff: "Nhân sự",
  tax: "Thuế",
  other: "Khác",
};
const OPERATING: ExpenseCategory[] = ["infrastructure", "ai_api", "payment_fee", "marketing", "staff", "other"];

type Line = { label: string; pick: (c: ProfitColumn) => string; tone?: "total" | "minus" | "result" };

const LINES: Line[] = [
  { label: "Giá niêm yết (GMV)", pick: (c) => c.list_amount },
  { label: "− Giảm giá", pick: (c) => c.discount, tone: "minus" },
  { label: "= Học viên trả", pick: (c) => c.collected, tone: "total" },
  { label: "− Hoa hồng giảng viên", pick: (c) => c.instructor_share, tone: "minus" },
  { label: "= Doanh thu sàn", pick: (c) => c.platform_revenue, tone: "total" },
  { label: "− Phí cổng thanh toán (ước tính)", pick: (c) => c.gateway_fee, tone: "minus" },
  ...OPERATING.map<Line>((category) => ({
    label: `− ${CATEGORY_LABELS[category]}`,
    pick: (c) => c.expenses[category],
    tone: "minus",
  })),
  { label: "= Lợi nhuận trước thuế", pick: (c) => c.profit_before_tax, tone: "total" },
  { label: "− Thuế", pick: (c) => c.tax, tone: "minus" },
  { label: "= Lợi nhuận giữ lại", pick: (c) => c.retained, tone: "result" },
];

/**
 * What the platform kept: a profit and loss statement for a year, by month or
 * quarter, accrued on the day orders were paid -- and the expenses an admin
 * records against it.
 */
export function ProfitPage() {
  const { accessToken } = useAuth();
  const thisYear = Number(vietnamToday().slice(0, 4));
  const [year, setYear] = useState(thisYear);
  const [granularity, setGranularity] = useState<"month" | "quarter">("month");

  const profit = useQuery({
    queryKey: [...PROFIT_KEY, year, granularity],
    queryFn: () => getProfit(accessToken as string, year, granularity),
    enabled: accessToken !== null,
    placeholderData: keepPreviousData,
  });

  return (
    <section className="space-y-6" aria-labelledby="profit-title">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 id="profit-title" className="font-semibold">
            Lợi nhuận giữ lại
          </h2>
          <p className="text-sm text-muted-foreground">
            Ghi nhận theo ngày đơn được thanh toán. Hoa hồng giảng viên và phí cổng tính tự động;
            các chi phí khác do quản trị viên nhập.
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <NativeSelect
            aria-label="Năm"
            value={year}
            onChange={(event) => setYear(Number(event.target.value))}
            className="h-9 w-24"
          >
            {Array.from({ length: 6 }, (_, i) => thisYear - i).map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </NativeSelect>
          <NativeSelect
            aria-label="Chia theo"
            value={granularity}
            onChange={(event) => setGranularity(event.target.value as "month" | "quarter")}
            className="h-9 w-36"
          >
            <option value="month">Theo tháng</option>
            <option value="quarter">Theo quý</option>
          </NativeSelect>
          <ExportButton path={profitPath(year, granularity, "/export.xlsx")} filename={`devpath_lai-lo_${year}.xlsx`} />
        </div>
      </div>

      {profit.isPending ? (
        <ListSkeleton rows={2} height="h-48" fill />
      ) : profit.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(profit.error)}</AlertDescription>
        </Alert>
      ) : (
        <div className={cn("space-y-4 transition-opacity", profit.isFetching && "opacity-60")}>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Tile label="Học viên trả (cả năm)" value={money(profit.data.total.collected)} />
            <Tile
              label="Doanh thu sàn"
              value={money(profit.data.total.platform_revenue)}
              note={`Take rate ${formatRate(profit.data.total.take_rate)}`}
            />
            <Tile
              label="Chi phí vận hành + phí cổng"
              value={money(
                String(Number(profit.data.total.operating_expenses) + Number(profit.data.total.gateway_fee)),
              )}
            />
            <Tile
              label="Lợi nhuận giữ lại"
              value={money(profit.data.total.retained)}
              note={`Biên ${formatRate(profit.data.total.net_margin)}`}
              tone={Number(profit.data.total.retained) < 0 ? "loss" : "gain"}
            />
          </div>
          <Card>
            <CardHeader>
              <CardTitle>Báo cáo lãi lỗ năm {profit.data.year}</CardTitle>
              <CardDescription>{profit.data.fee_source}</CardDescription>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <table className="w-full min-w-[1180px] text-sm">
                <thead>
                  <tr className="border-b text-left text-xs text-muted-foreground">
                    <th className="sticky left-0 min-w-64 bg-card py-2 pr-3 font-medium">Khoản mục</th>
                    {profit.data.columns.map((column) => (
                      <th key={column.start} className="px-2 py-2 text-right font-medium">
                        {granularity === "quarter"
                          ? `Quý ${Math.floor(Number(column.start.slice(5, 7)) / 3) + 1}`
                          : `T${Number(column.start.slice(5, 7))}`}
                      </th>
                    ))}
                    <th className="py-2 pl-3 text-right font-medium">Cả năm</th>
                  </tr>
                </thead>
                <tbody>
                  {LINES.map((line) => (
                    <tr
                      key={line.label}
                      className={cn(
                        "border-b last:border-0",
                        line.tone === "total" && "font-medium",
                        line.tone === "result" && "bg-muted/40 font-semibold",
                      )}
                    >
                      <th
                        scope="row"
                        className={cn(
                          "sticky left-0 min-w-64 bg-card py-1.5 pr-3 text-left font-[inherit]",
                          line.tone === "minus" && "text-muted-foreground",
                        )}
                      >
                        {line.label}
                      </th>
                      {profit.data.columns.map((column) => (
                        <ProfitCell key={column.start} value={line.pick(column)} />
                      ))}
                      <ProfitCell value={line.pick(profit.data.total)} />
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        </div>
      )}

      <Expenses year={year} />
    </section>
  );
}

function ProfitCell({ value }: { value: string }) {
  const amount = Number(value);
  return (
    <td
      className={cn(
        "px-2 py-1.5 text-right tabular-nums",
        amount === 0 && "text-muted-foreground/60",
        amount < 0 && "text-red-700 dark:text-red-400",
      )}
    >
      {amount === 0 ? "–" : new Intl.NumberFormat("vi-VN").format(amount)}
    </td>
  );
}

function Tile({
  label,
  value,
  note,
  tone,
}: {
  label: string;
  value: string;
  note?: string;
  tone?: "gain" | "loss";
}) {
  return (
    <div className="rounded-lg border bg-card p-4">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p
        className={cn(
          "mt-1 text-2xl font-semibold tracking-tight",
          tone === "loss" && "text-red-700 dark:text-red-400",
        )}
      >
        {value}
      </p>
      {note ? <p className="mt-1 text-xs text-muted-foreground">{note}</p> : null}
    </div>
  );
}

function Expenses({ year }: { year: number }) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const [month, setMonth] = useState<number | null>(null);
  const [category, setCategory] = useState<ExpenseCategory | "">("");
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<Expense | "new" | null>(null);

  const params = { year, month, category, page };
  const expenses = useQuery({
    queryKey: [...PROFIT_KEY, "expenses", params],
    queryFn: () => listExpenses(accessToken as string, params),
    enabled: accessToken !== null,
    placeholderData: keepPreviousData,
  });
  const remove = useMutation({
    mutationFn: (id: string) => deleteExpense(accessToken as string, id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: PROFIT_KEY }),
  });

  return (
    <Card>
      <CardHeader className="gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <CardTitle>Chi phí năm {year}</CardTitle>
          <CardDescription>
            {expenses.data ? `Tổng theo bộ lọc: ${money(expenses.data.amount)}` : "Các khoản chi theo hóa đơn."}
          </CardDescription>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <NativeSelect
            aria-label="Tháng"
            value={month ?? ""}
            onChange={(event) => {
              setMonth(event.target.value ? Number(event.target.value) : null);
              setPage(1);
            }}
            className="h-9 w-32"
          >
            <option value="">Cả năm</option>
            {Array.from({ length: 12 }, (_, i) => i + 1).map((value) => (
              <option key={value} value={value}>
                Tháng {value}
              </option>
            ))}
          </NativeSelect>
          <NativeSelect
            aria-label="Nhóm"
            value={category}
            onChange={(event) => {
              setCategory(event.target.value as ExpenseCategory | "");
              setPage(1);
            }}
            className="h-9 w-52"
          >
            <option value="">Mọi nhóm</option>
            {(Object.keys(CATEGORY_LABELS) as ExpenseCategory[]).map((value) => (
              <option key={value} value={value}>
                {CATEGORY_LABELS[value]}
              </option>
            ))}
          </NativeSelect>
          <ExportButton path={expensesPath({ year, month, category }, "/export.xlsx")} filename="devpath_chi-phi.xlsx" />
          <Button size="sm" onClick={() => setEditing("new")}>
            <Plus aria-hidden />
            Thêm khoản chi
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {expenses.isPending ? (
          <ListSkeleton rows={3} height="h-10" />
        ) : expenses.isError ? (
          <Alert variant="destructive">
            <AlertDescription>{apiErrorMessage(expenses.error)}</AlertDescription>
          </Alert>
        ) : expenses.data.items.length === 0 ? (
          <EmptyState title="Chưa có khoản chi nào" hint="Thêm hóa đơn máy chủ, API AI, marketing… để tính lợi nhuận." />
        ) : (
          <div className="relative overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead>
                <tr className="border-b text-left text-xs text-muted-foreground">
                  <th className="py-2 pr-3 font-medium">Ngày</th>
                  <th className="px-3 py-2 font-medium">Nhóm</th>
                  <th className="px-3 py-2 font-medium">Mô tả</th>
                  <th className="px-3 py-2 text-right font-medium">Số tiền</th>
                  <th className="py-2 pl-3">
                    <span className="sr-only">Thao tác</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {expenses.data.items.map((expense) => (
                  <tr key={expense.id} className="border-b last:border-0">
                    <td className="py-2 pr-3 tabular-nums">{day(expense.incurred_on)}</td>
                    <td className="px-3 py-2">{CATEGORY_LABELS[expense.category]}</td>
                    <td className="px-3 py-2">{expense.description}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{money(expense.amount)}</td>
                    <td className="py-2 pl-3 text-right whitespace-nowrap">
                      <Button variant="ghost" size="icon" className="size-8" onClick={() => setEditing(expense)} aria-label="Sửa khoản chi">
                        <Pencil className="size-4" aria-hidden />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-8"
                        onClick={() => remove.mutate(expense.id)}
                        disabled={remove.isPending}
                        aria-label="Xóa khoản chi"
                      >
                        <Trash2 className="size-4" aria-hidden />
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {expenses.data ? (
          <Pager page={page} pageSize={expenses.data.page_size} total={expenses.data.total} onPage={setPage} />
        ) : null}
      </CardContent>
      <ExpenseDialog expense={editing} year={year} onClose={() => setEditing(null)} />
    </Card>
  );
}

function ExpenseDialog({
  expense,
  year,
  onClose,
}: {
  expense: Expense | "new" | null;
  year: number;
  onClose: () => void;
}) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const blank: ExpenseInput = {
    incurred_on: String(year) === vietnamToday().slice(0, 4) ? vietnamToday() : `${year}-12-31`,
    category: "infrastructure",
    description: "",
    amount: "",
  };
  const [form, setForm] = useState<ExpenseInput>(blank);
  const [last, setLast] = useState<typeof expense>(null);

  if (expense !== last) {
    setLast(expense);
    if (expense === "new") setForm(blank);
    else if (expense)
      setForm({
        incurred_on: expense.incurred_on,
        category: expense.category,
        description: expense.description,
        amount: String(Number(expense.amount)),
      });
  }

  const save = useMutation({
    mutationFn: () =>
      expense === "new"
        ? createExpense(accessToken as string, form)
        : updateExpense(accessToken as string, (expense as Expense).id, form),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: PROFIT_KEY });
      onClose();
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    save.mutate();
  }

  return (
    <Dialog open={expense !== null} onOpenChange={(open) => (open ? null : onClose())}>
      <DialogContent size="form">
        <form onSubmit={submit} className="space-y-4">
          <DialogHeader>
            <DialogTitle>{expense === "new" ? "Thêm khoản chi" : "Sửa khoản chi"}</DialogTitle>
            <DialogDescription>Ghi theo ngày phát sinh trên hóa đơn.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1">
              <Label htmlFor="expense-date">Ngày</Label>
              <Input
                id="expense-date"
                type="date"
                value={form.incurred_on}
                onChange={(event) => setForm({ ...form, incurred_on: event.target.value })}
                required
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="expense-amount">Số tiền (₫)</Label>
              <Input
                id="expense-amount"
                inputMode="numeric"
                value={form.amount}
                onChange={(event) => setForm({ ...form, amount: event.target.value.replace(/[^\d.]/g, "") })}
                required
              />
            </div>
          </div>
          <div className="space-y-1">
            <Label htmlFor="expense-category">Nhóm</Label>
            <NativeSelect
              id="expense-category"
              value={form.category}
              onChange={(event) => setForm({ ...form, category: event.target.value as ExpenseCategory })}
            >
              {(Object.keys(CATEGORY_LABELS) as ExpenseCategory[]).map((value) => (
                <option key={value} value={value}>
                  {CATEGORY_LABELS[value]}
                </option>
              ))}
            </NativeSelect>
          </div>
          <div className="space-y-1">
            <Label htmlFor="expense-description">Mô tả</Label>
            <Input
              id="expense-description"
              value={form.description}
              onChange={(event) => setForm({ ...form, description: event.target.value })}
              maxLength={200}
              required
              placeholder="Ví dụ: Máy chủ Azure tháng 10"
            />
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
