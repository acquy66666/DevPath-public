"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { ADMIN_KEY } from "@/components/admin/admin-nav";
import { ListSkeleton } from "@/components/admin/admin-shared";
import { ColumnChart, type Column } from "@/components/instructor/stats/column-chart";
import { formatCompact, formatCount, formatRate } from "@/components/instructor/stats/format";
import { StatTile } from "@/components/instructor/stats/stat-tile";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ExportButton } from "@/components/ui/export-button";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { apiErrorMessage } from "@/lib/api/error-messages";
import {
  getRevenue,
  getRevenueBreakdown,
  GRANULARITIES,
  listEvaluations,
  revenuePath,
  type FinanceGranularity,
  type Money,
} from "@/lib/api/finance";
import { useAuth } from "@/lib/auth/auth-provider";
import { cn } from "@/lib/utils";

import {
  addDays,
  bucketName,
  DateRangePicker,
  day,
  daysBetween,
  money,
  MoneyCell,
  vietnamToday,
  type DateRange,
} from "./finance-shared";

const METRICS: { key: keyof Money; label: string; note: string }[] = [
  { key: "paid", label: "Học viên trả", note: "Số tiền học viên thực trả, sau mã giảm giá." },
  {
    key: "instructor_share",
    label: "Hoa hồng giảng viên",
    note: "Phần của giảng viên theo tỉ lệ chốt lúc bán, làm tròn xuống tới đồng.",
  },
  {
    key: "platform_share",
    label: "Phần sàn giữ",
    note: "Học viên trả trừ hoa hồng giảng viên, chưa trừ phí cổng thanh toán.",
  },
  { key: "orders", label: "Số đơn", note: "Đơn đã thanh toán." },
];

/**
 * Revenue for any range, cut by hour up to year, for the whole platform or
 * one instructor -- with the range of the same length before it, the split
 * between instructors and the platform, and who and what it came from.
 */
export function RevenuePage() {
  const { accessToken } = useAuth();
  const today = vietnamToday();
  const [range, setRange] = useState<DateRange>({ start: addDays(today, -29), end: today });
  const [granularity, setGranularity] = useState<FinanceGranularity>("day");
  const [instructorId, setInstructorId] = useState<string>("");
  const [metric, setMetric] = useState(METRICS[0]);

  const span = daysBetween(range.start, range.end);
  // A bucket size the range is too long for falls back to the next one up.
  const effective =
    GRANULARITIES.find((g) => g.value === granularity && span <= g.maxDays)?.value ??
    GRANULARITIES.find((g) => span <= g.maxDays && g.value !== "hour")?.value ??
    "year";

  const params = { ...range, granularity: effective, instructorId: instructorId || null };

  const instructors = useQuery({
    queryKey: [...ADMIN_KEY, "tiers", "evaluations"],
    queryFn: () => listEvaluations(accessToken as string),
    enabled: accessToken !== null,
  });
  const revenue = useQuery({
    queryKey: [...ADMIN_KEY, "finance", "revenue", params],
    queryFn: () => getRevenue(accessToken as string, params),
    enabled: accessToken !== null,
    placeholderData: keepPreviousData,
  });
  const breakdown = useQuery({
    queryKey: [...ADMIN_KEY, "finance", "breakdown", range, instructorId],
    queryFn: () =>
      getRevenueBreakdown(accessToken as string, { ...range, instructorId: instructorId || null }),
    enabled: accessToken !== null,
    placeholderData: keepPreviousData,
  });

  const columns: Column[] = (revenue.data?.series ?? []).map((point) => {
    const name = bucketName(point.bucket, effective);
    const value = Number(point[metric.key]);
    return {
      key: point.bucket,
      tick: name.tick,
      label: name.label,
      value,
      display: metric.key === "orders" ? `${formatCount(value)} đơn` : money(String(value)),
      detail: `${formatCount(point.orders)} đơn · ${money(point.paid)} học viên trả`,
    };
  });

  const data = revenue.data;
  const previousLabel = data ? `${day(data.previous_start)} – ${day(data.previous_end)}` : "";

  return (
    <section className="space-y-6" aria-labelledby="revenue-title">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 id="revenue-title" className="font-semibold">
            Doanh thu theo thời gian
          </h2>
          <p className="text-sm text-muted-foreground">
            Theo lúc đơn được thanh toán, giờ Việt Nam. So với khoảng cùng độ dài ngay trước.
          </p>
        </div>
        <ExportButton path={revenuePath(params, "/export.xlsx")} filename="devpath_doanh-thu.xlsx" />
      </div>

      <div className="flex flex-wrap items-end gap-4 rounded-lg border p-4">
        <DateRangePicker value={range} onChange={setRange} />
        <div className="space-y-1">
          <Label htmlFor="granularity" className="text-xs">
            Gom theo
          </Label>
          <NativeSelect
            id="granularity"
            value={effective}
            onChange={(event) => setGranularity(event.target.value as FinanceGranularity)}
            className="h-9 w-28"
          >
            {GRANULARITIES.map((option) => (
              <option key={option.value} value={option.value} disabled={span > option.maxDays}>
                {option.label}
              </option>
            ))}
          </NativeSelect>
        </div>
        <div className="min-w-[min(100%,16rem)] flex-1 space-y-1">
          <Label htmlFor="instructor" className="text-xs">
            Giảng viên
          </Label>
          <NativeSelect
            id="instructor"
            value={instructorId}
            onChange={(event) => setInstructorId(event.target.value)}
            className="h-9"
          >
            <option value="">Toàn sàn</option>
            {(instructors.data ?? []).map((row) => (
              <option key={row.instructor.id} value={row.instructor.id}>
                {row.instructor.full_name} · {row.current.name}
              </option>
            ))}
          </NativeSelect>
        </div>
      </div>

      {revenue.isPending ? (
        <ListSkeleton rows={2} height="h-40" fill />
      ) : revenue.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(revenue.error)}</AlertDescription>
        </Alert>
      ) : data ? (
        <div className={cn("space-y-6 transition-opacity", revenue.isFetching && "opacity-60")}>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {METRICS.map((item) => (
              <StatTile
                key={item.key}
                label={item.label}
                value={
                  item.key === "orders"
                    ? formatCount(Number(data.totals[item.key]))
                    : money(String(data.totals[item.key]))
                }
                current={Number(data.totals[item.key])}
                previous={Number(data.previous[item.key])}
                previousLabel={previousLabel}
                previousDisplay={
                  item.key === "orders"
                    ? formatCount(Number(data.previous[item.key]))
                    : money(String(data.previous[item.key]))
                }
              />
            ))}
          </div>
          <p className="text-sm text-muted-foreground">
            Giá niêm yết (GMV) {money(data.totals.list_amount)} − giảm giá{" "}
            {money(data.totals.discount)} = học viên trả {money(data.totals.paid)} ·{" "}
            {formatCount(data.totals.lines)} dòng bán · {formatCount(data.totals.buyers)} người mua
            {data.instructor ? ` · chỉ ${data.instructor.full_name}` : ""}.
          </p>

          <Card>
            <CardHeader className="gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <CardTitle>{metric.label}</CardTitle>
                <CardDescription>{metric.note}</CardDescription>
              </div>
              <div role="group" aria-label="Số liệu trên biểu đồ" className="flex flex-wrap gap-1">
                {METRICS.map((option) => (
                  <button
                    key={option.key}
                    type="button"
                    aria-pressed={option.key === metric.key}
                    onClick={() => setMetric(option)}
                    className={cn(
                      "rounded-md border px-2.5 py-1 text-xs transition-colors focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none",
                      option.key === metric.key
                        ? "border-primary bg-primary text-primary-foreground"
                        : "text-muted-foreground hover:text-foreground",
                    )}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </CardHeader>
            <CardContent>
              <ColumnChart
                columns={columns}
                formatTick={formatCompact}
                integer={metric.key === "orders"}
                label={metric.label}
                emptyNote="Không có đơn nào được thanh toán trong khoảng này."
              />
            </CardContent>
          </Card>
        </div>
      ) : null}

      {breakdown.data ? (
        <>
          {breakdown.data.instructors.length > 0 ? (
            <Card>
              <CardHeader>
                <CardTitle>Theo giảng viên</CardTitle>
                <CardDescription>Bấm tên để xem riêng doanh thu của giảng viên đó.</CardDescription>
              </CardHeader>
              <CardContent className="overflow-x-auto">
                <table className="w-full min-w-[760px] text-sm">
                  <thead>
                    <tr className="border-b text-left text-xs text-muted-foreground">
                      <th className="py-2 pr-3 font-medium">Giảng viên</th>
                      <th className="px-3 py-2 font-medium">Cấp</th>
                      <th className="px-3 py-2 text-right font-medium">Dòng bán</th>
                      <th className="px-3 py-2 text-right font-medium">Học viên trả</th>
                      <th className="px-3 py-2 text-right font-medium">Hoa hồng GV</th>
                      <th className="px-3 py-2 text-right font-medium">Phần sàn</th>
                      <th className="py-2 pl-3 text-right font-medium">Tỉ trọng</th>
                    </tr>
                  </thead>
                  <tbody>
                    {breakdown.data.instructors.map((row) => (
                      <tr key={row.instructor.id} className="border-b last:border-0">
                        <th scope="row" className="py-2 pr-3 text-left font-normal">
                          <button
                            type="button"
                            className="font-medium hover:underline"
                            onClick={() => setInstructorId(row.instructor.id)}
                          >
                            {row.instructor.full_name}
                          </button>
                          <span className="block text-xs text-muted-foreground">
                            {row.instructor.email}
                          </span>
                        </th>
                        <td className="px-3 py-2">
                          {row.tier.name}{" "}
                          <span className="text-xs text-muted-foreground">
                            ({formatRate(Number(row.tier.share_rate))})
                          </span>
                        </td>
                        <td className="px-3 py-2 text-right tabular-nums">{formatCount(row.lines)}</td>
                        <MoneyCell value={row.paid} />
                        <MoneyCell value={row.instructor_share} />
                        <MoneyCell value={row.platform_share} muted />
                        <td className="py-2 pl-3 text-right tabular-nums">
                          {formatRate(row.share_of_paid)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </CardContent>
            </Card>
          ) : null}
          <Card>
            <CardHeader>
              <CardTitle>Theo khóa học</CardTitle>
              <CardDescription>
                {day(breakdown.data.start)} – {day(breakdown.data.end)}
              </CardDescription>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              {breakdown.data.courses.length === 0 ? (
                <p className="py-6 text-center text-sm text-muted-foreground">
                  Không có khóa học nào bán được trong khoảng này.
                </p>
              ) : (
                <table className="w-full min-w-[720px] text-sm">
                  <thead>
                    <tr className="border-b text-left text-xs text-muted-foreground">
                      <th className="py-2 pr-3 font-medium">Khóa học</th>
                      <th className="px-3 py-2 text-right font-medium">Lượt bán</th>
                      <th className="px-3 py-2 text-right font-medium">Giảm giá</th>
                      <th className="px-3 py-2 text-right font-medium">Học viên trả</th>
                      <th className="px-3 py-2 text-right font-medium">Hoa hồng GV</th>
                      <th className="py-2 pl-3 text-right font-medium">Phần sàn</th>
                    </tr>
                  </thead>
                  <tbody>
                    {breakdown.data.courses.map((row) => (
                      <tr key={row.course_id} className="border-b last:border-0">
                        <th scope="row" className="max-w-72 py-2 pr-3 text-left font-normal">
                          <span className="line-clamp-2 font-medium">{row.course_title}</span>
                          <span className="block text-xs text-muted-foreground">
                            {row.instructor.full_name}
                          </span>
                        </th>
                        <td className="px-3 py-2 text-right tabular-nums">{formatCount(row.lines)}</td>
                        <MoneyCell value={row.discount} muted />
                        <MoneyCell value={row.paid} />
                        <MoneyCell value={row.instructor_share} />
                        <td className="py-2 pl-3 text-right tabular-nums text-muted-foreground">
                          {money(row.platform_share)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </CardContent>
          </Card>
        </>
      ) : breakdown.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(breakdown.error)}</AlertDescription>
        </Alert>
      ) : null}
    </section>
  );
}
