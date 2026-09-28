"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { CourseStatusBadge } from "@/components/instructor/course-status-badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { listCourseStats, type StatsPeriod } from "@/lib/api/instructor-stats";
import { formatAmount } from "@/lib/format";
import { cn } from "@/lib/utils";

import { formatCount, formatRate } from "./format";

/**
 * Every course in one table, best seller of the period first.
 *
 * Numbers are right-aligned in tabular figures so a column can be read down.
 * Progress gets a meter beside its percentage: the meter is what a reader
 * scans, the number is what they quote. On a phone the table scrolls
 * sideways inside its card rather than squeezing seven columns to nothing.
 */
export function CourseStatsTable({
  accessToken,
  period,
  periodLabel,
}: {
  accessToken: string;
  period: StatsPeriod;
  periodLabel: string;
}) {
  // The parent keys this on the period, so a new period starts again at page
  // 1: page 3 of a different ranking is a different set of courses.
  const [page, setPage] = useState(1);

  const query = useQuery({
    queryKey: ["instructor-stats", "courses", period, page],
    queryFn: () => listCourseStats(accessToken, period, page),
    placeholderData: keepPreviousData,
  });

  if (query.isPending) {
    return <div className="h-48 animate-pulse rounded-lg bg-muted/40" />;
  }

  if (query.isError) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{apiErrorMessage(query.error)}</AlertDescription>
      </Alert>
    );
  }

  const { items, total, page_size } = query.data;
  const pageCount = Math.max(1, Math.ceil(total / page_size));

  if (items.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        Chưa có khóa học nào để thống kê.
      </p>
    );
  }

  return (
    <div className={cn("space-y-4 transition-opacity", query.isFetching && "opacity-60")}>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] text-sm">
          <thead>
            <tr className="border-b text-left text-xs text-muted-foreground">
              <th scope="col" className="py-2 pr-4 font-medium">Khóa học</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Học viên</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">
                Mới ({periodLabel})
              </th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Hoàn thành</th>
              <th scope="col" className="px-3 py-2 font-medium">Tiến độ TB</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">
                Doanh thu ({periodLabel})
              </th>
              <th scope="col" className="py-2 pl-3 text-right font-medium">Tổng doanh thu</th>
            </tr>
          </thead>
          <tbody>
            {items.map((row) => (
              <tr key={row.course.id} className="border-b last:border-0 align-top">
                <th scope="row" className="max-w-72 py-3 pr-4 text-left font-normal">
                  <Link
                    href={`/giang-day/${row.course.id}`}
                    className="line-clamp-2 font-medium hover:underline"
                  >
                    {row.course.title}
                  </Link>
                  <div className="mt-1 flex flex-wrap gap-1">
                    <CourseStatusBadge status={row.course.status} />
                    {row.course.is_deleted ? <Badge variant="outline">Đã gỡ</Badge> : null}
                  </div>
                </th>
                <td className="px-3 py-3 text-right tabular-nums">{formatCount(row.students)}</td>
                <td className="px-3 py-3 text-right tabular-nums">
                  {formatCount(row.new_enrollments)}
                </td>
                <td className="px-3 py-3 text-right tabular-nums">
                  {formatRate(row.completion_rate)}
                  {row.students > 0 ? (
                    <span className="block text-xs text-muted-foreground">
                      {formatCount(row.completed)}/{formatCount(row.students)}
                    </span>
                  ) : null}
                </td>
                <td className="px-3 py-3">
                  <Meter value={row.avg_progress} />
                </td>
                <td className="px-3 py-3 text-right tabular-nums">
                  {formatAmount(row.revenue)}
                  {row.sales > 0 ? (
                    <span className="block text-xs text-muted-foreground">
                      {formatCount(row.sales)} lượt bán
                    </span>
                  ) : null}
                </td>
                <td className="py-3 pl-3 text-right tabular-nums">
                  {formatAmount(row.revenue_all_time)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {pageCount > 1 ? (
        <div className="flex items-center justify-center gap-3">
          <Button
            variant="outline"
            size="sm"
            disabled={page === 1}
            onClick={() => setPage((current) => current - 1)}
          >
            Trang trước
          </Button>
          <span className="text-sm text-muted-foreground">
            Trang {page} / {pageCount}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= pageCount}
            onClick={() => setPage((current) => current + 1)}
          >
            Trang sau
          </Button>
        </div>
      ) : null}
    </div>
  );
}

/** A thin bar for a 0–1 ratio, its track a lighter step of the same ink. */
function Meter({ value }: { value: number | null }) {
  return (
    <div className="flex items-center gap-2">
      <div
        role="meter"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={value === null ? undefined : Math.round(value * 100)}
        aria-label="Tiến độ trung bình"
        className="h-1.5 w-20 overflow-hidden rounded-full bg-primary/15"
      >
        <div
          className="h-full rounded-full bg-primary"
          style={{ width: `${(value ?? 0) * 100}%` }}
        />
      </div>
      <span className="text-right tabular-nums">{formatRate(value)}</span>
    </div>
  );
}
