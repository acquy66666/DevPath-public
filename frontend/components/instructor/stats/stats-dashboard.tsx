"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ArrowLeft, BarChart3, Plus } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { apiErrorMessage } from "@/lib/api/error-messages";
import {
  getInstructorOverview,
  STATS_PERIODS,
  type InstructorOverview,
  type StatsPeriod,
} from "@/lib/api/instructor-stats";
import { useAuth } from "@/lib/auth/auth-provider";
import { formatAmount } from "@/lib/format";
import { cn } from "@/lib/utils";

import { ColumnChart, type Column } from "./column-chart";
import { CourseStatsTable } from "./course-stats-table";
import {
  bucketLabel,
  bucketTick,
  formatCompact,
  formatCount,
  formatDay,
  formatRate,
} from "./format";
import { StatTile } from "./stat-tile";

/**
 * The instructor's dashboard: one period picker scoping everything under it.
 *
 * Changing the period keeps the previous numbers on screen, dimmed, until the
 * new ones arrive -- the frame holds still instead of flashing back to
 * skeletons, and the reader's eye stays where it was.
 */
export function StatsDashboard() {
  const { accessToken } = useAuth();
  const [period, setPeriod] = useState<StatsPeriod>("30d");
  const choice = STATS_PERIODS.find((option) => option.value === period)!;

  const query = useQuery({
    queryKey: ["instructor-stats", "overview", period],
    queryFn: () => getInstructorOverview(accessToken as string, period),
    enabled: accessToken !== null,
    placeholderData: keepPreviousData,
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <Link
            href="/giang-day"
            className="mb-2 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="size-4" aria-hidden />
            Khóa học của tôi
          </Link>
          <h1 className="text-2xl font-semibold tracking-tight">Thống kê giảng dạy</h1>
          <p className="text-sm text-muted-foreground">
            {query.data
              ? `${formatDay(query.data.start)} – ${formatDay(query.data.end)} · giờ Việt Nam`
              : "Doanh thu, học viên mới và tỉ lệ hoàn thành của các khóa học bạn dạy."}
          </p>
        </div>
        <PeriodPicker value={period} onChange={setPeriod} />
      </div>

      {query.isPending ? (
        <Skeleton />
      ) : query.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(query.error)}</AlertDescription>
        </Alert>
      ) : query.data.courses_count === 0 && query.data.students_total === 0 ? (
        <EmptyState />
      ) : (
        <div className={cn("space-y-6 transition-opacity", query.isFetching && "opacity-60")}>
          <Overview data={query.data} previousLabel={choice.previous} />
          <Card>
            <CardHeader>
              <CardTitle>Theo từng khóa học</CardTitle>
              <CardDescription>
                Học viên, hoàn thành và tiến độ tính từ trước tới nay; ghi danh mới và doanh
                thu tính trong {choice.label} gần nhất.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <CourseStatsTable
                key={period}
                accessToken={accessToken as string}
                period={period}
                periodLabel={choice.label}
              />
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}

function Overview({
  data,
  previousLabel,
}: {
  data: InstructorOverview;
  previousLabel: string;
}) {
  const unit = data.granularity === "day" ? "ngày" : "tháng";

  const revenueColumns: Column[] = data.series.map((point) => ({
    key: point.bucket,
    tick: bucketTick(point.bucket, data.granularity),
    label: bucketLabel(point.bucket, data.granularity),
    value: Number(point.revenue),
    display: formatAmount(point.revenue),
    detail: `${formatCount(point.sales)} lượt bán`,
  }));

  const studentColumns: Column[] = data.series.map((point) => ({
    key: point.bucket,
    tick: bucketTick(point.bucket, data.granularity),
    label: bucketLabel(point.bucket, data.granularity),
    value: point.new_students,
    display: `${formatCount(point.new_students)} học viên mới`,
    detail: `${formatCount(point.enrollments)} lượt ghi danh`,
  }));

  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile
          label="Doanh thu"
          value={formatAmount(data.current.revenue)}
          current={Number(data.current.revenue)}
          previous={Number(data.previous.revenue)}
          previousLabel={previousLabel}
          previousDisplay={formatAmount(data.previous.revenue)}
        />
        <StatTile
          label="Lượt bán khóa học"
          value={formatCount(data.current.sales)}
          current={data.current.sales}
          previous={data.previous.sales}
          previousLabel={previousLabel}
          previousDisplay={formatCount(data.previous.sales)}
        />
        <StatTile
          label="Học viên mới"
          value={formatCount(data.current.new_students)}
          current={data.current.new_students}
          previous={data.previous.new_students}
          previousLabel={previousLabel}
          previousDisplay={formatCount(data.previous.new_students)}
          note={`${formatCount(data.current.enrollments)} lượt ghi danh`}
        />
        <StatTile
          label="Tỉ lệ hoàn thành"
          value={formatRate(data.completion_rate)}
          note={`Từ trước tới nay, trên ${formatCount(data.students_total)} học viên`}
        />
      </div>

      <p className="text-sm text-muted-foreground">
        Từ trước tới nay: <span className="text-foreground">{formatAmount(data.revenue_all_time)}</span>{" "}
        doanh thu · {formatCount(data.students_total)} học viên · {formatCount(data.courses_count)}{" "}
        khóa học. Doanh thu là số tiền học viên thực trả sau mã giảm giá, chưa trừ phí nền tảng.
      </p>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Doanh thu theo {unit}</CardTitle>
            <CardDescription>Tính theo lúc cổng thanh toán xác nhận đã nhận tiền.</CardDescription>
          </CardHeader>
          <CardContent>
            <ColumnChart
              columns={revenueColumns}
              formatTick={formatCompact}
              label={`Doanh thu theo ${unit}`}
              emptyNote="Chưa có đơn hàng nào được thanh toán trong kỳ này."
            />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Học viên mới theo {unit}</CardTitle>
            <CardDescription>
              Người lần đầu ghi danh một khóa học của bạn — học hai khóa vẫn tính là một.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ColumnChart
              columns={studentColumns}
              formatTick={formatCount}
              integer
              label={`Học viên mới theo ${unit}`}
              emptyNote="Chưa có học viên mới trong kỳ này."
            />
          </CardContent>
        </Card>
      </div>
    </>
  );
}

function PeriodPicker({
  value,
  onChange,
}: {
  value: StatsPeriod;
  onChange: (period: StatsPeriod) => void;
}) {
  return (
    <div role="group" aria-label="Khoảng thời gian" className="inline-flex rounded-lg border p-0.5">
      {STATS_PERIODS.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={option.value === value}
          onClick={() => onChange(option.value)}
          className={cn(
            "rounded-md px-3 py-1.5 text-sm transition-colors focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none",
            option.value === value
              ? "bg-primary text-primary-foreground"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

function Skeleton() {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[0, 1, 2, 3].map((tile) => (
          <div key={tile} className="h-24 animate-pulse rounded-xl border bg-muted/40" />
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        {[0, 1].map((chart) => (
          <div key={chart} className="h-72 animate-pulse rounded-xl border bg-muted/40" />
        ))}
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <Card>
      <CardHeader>
        <div className="mb-2 flex size-10 items-center justify-center rounded-lg bg-muted">
          <BarChart3 className="size-5 text-muted-foreground" aria-hidden />
        </div>
        <CardTitle>Chưa có gì để thống kê</CardTitle>
        <CardDescription>
          Số liệu xuất hiện ở đây khi khóa học đầu tiên của bạn có người ghi danh hoặc mua.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Button asChild>
          <Link href="/giang-day/moi">
            <Plus aria-hidden />
            Tạo khóa học
          </Link>
        </Button>
      </CardContent>
    </Card>
  );
}
