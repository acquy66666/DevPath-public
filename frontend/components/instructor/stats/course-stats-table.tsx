"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ListOrdered } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { CourseStatusBadge } from "@/components/instructor/course-status-badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Pager } from "@/components/ui/pager";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { listCourseStats, type CourseStats, type StatsPeriod } from "@/lib/api/instructor-stats";
import { cn } from "@/lib/utils";

import { CourseFunnelDialog } from "./course-funnel";
import { formatCount, formatRate, formatRating } from "./format";

const PAGE_SIZE = 10;

/**
 * Every course in one table, most students first -- the instructor compares
 * their own courses, never themselves with anybody else.
 *
 * Numbers are right-aligned in tabular figures so a column can be read down;
 * progress and completion get a meter, which is what a reader scans. "Theo
 * bài" opens where learners of that course stop, lesson by lesson.
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
  // The parent keys this on the period, so a new period starts again at page 1.
  const [page, setPage] = useState(1);
  const [funnel, setFunnel] = useState<CourseStats | null>(null);

  const query = useQuery({
    queryKey: ["instructor-stats", "courses", period, page],
    queryFn: () => listCourseStats(accessToken, { period, page, pageSize: PAGE_SIZE }),
    placeholderData: keepPreviousData,
  });

  if (query.isPending) {
    return <Skeleton className="h-48" />;
  }

  if (query.isError) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{apiErrorMessage(query.error)}</AlertDescription>
      </Alert>
    );
  }

  const { items, total } = query.data;

  if (items.length === 0) {
    return (
      <EmptyState mood="empty-courses" size="md" framed={false} title="Chưa có khóa học nào để thống kê" />
    );
  }

  return (
    <div className={cn("space-y-4 transition-opacity", query.isFetching && "opacity-60")}>
      <div className="relative overflow-x-auto">
        <table className="w-full min-w-[920px] text-sm">
          <thead>
            <tr className="border-b text-left text-xs text-muted-foreground">
              <th scope="col" className="py-2 pr-4 font-medium">Khóa học</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Học viên</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">
                Mới ({periodLabel})
              </th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Bắt đầu học</th>
              <th scope="col" className="px-3 py-2 font-medium">Hoàn thành</th>
              <th scope="col" className="px-3 py-2 font-medium">Tiến độ TB</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Đánh giá</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Quiz đạt lần đầu</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Code giải được</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Câu hỏi chờ</th>
              <th scope="col" className="py-2 pl-3 text-right font-medium">
                <span className="sr-only">Chi tiết</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {items.map((row) => (
              <tr key={row.course.id} className="border-b align-top last:border-0">
                <th scope="row" className="max-w-64 py-3 pr-4 text-left font-normal">
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
                <td className="px-3 py-3 text-right tabular-nums">
                  {formatCount(row.students)}
                  {row.wishlisted > 0 ? (
                    <span className="block text-xs text-muted-foreground">
                      {formatCount(row.wishlisted)} yêu thích
                    </span>
                  ) : null}
                </td>
                <td className="px-3 py-3 text-right tabular-nums">
                  {formatCount(row.new_enrollments)}
                </td>
                <td className="px-3 py-3 text-right tabular-nums">{formatRate(row.started_rate)}</td>
                <td className="px-3 py-3">
                  <Meter value={row.completion_rate} label="Tỉ lệ hoàn thành" />
                  {row.students > 0 ? (
                    <span className="block text-xs text-muted-foreground tabular-nums">
                      {formatCount(row.completed)}/{formatCount(row.students)}
                    </span>
                  ) : null}
                </td>
                <td className="px-3 py-3">
                  <Meter value={row.avg_progress} label="Tiến độ trung bình" />
                </td>
                <td className="px-3 py-3 text-right tabular-nums">
                  {formatRating(row.rating_avg)}
                  <span className="block text-xs text-muted-foreground">
                    {formatCount(row.rating_count)} đánh giá
                  </span>
                </td>
                <td className="px-3 py-3 text-right tabular-nums">
                  {formatRate(row.quiz_first_try_pass_rate)}
                </td>
                <td className="px-3 py-3 text-right tabular-nums">
                  {formatRate(row.code_solve_rate)}
                </td>
                <td
                  className={cn(
                    "px-3 py-3 text-right tabular-nums",
                    row.open_questions > 0 && "font-medium text-warning-text",
                  )}
                >
                  {formatCount(row.open_questions)}
                </td>
                <td className="py-3 pl-3 text-right">
                  <Button variant="ghost" size="sm" onClick={() => setFunnel(row)}>
                    <ListOrdered aria-hidden />
                    Theo bài
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Pager page={page} pageSize={PAGE_SIZE} total={total} onPage={setPage} />

      <CourseFunnelDialog
        accessToken={accessToken}
        course={funnel?.course ?? null}
        onClose={() => setFunnel(null)}
      />
    </div>
  );
}

/** A thin bar for a 0–1 ratio, its track a lighter step of the same ink. */
export function Meter({ value, label }: { value: number | null; label: string }) {
  return (
    <div className="flex items-center gap-2">
      {/* No value yet (nobody enrolled): a meter must carry one, so the bar is
          decoration and the "—" beside it says so. */}
      <div
        {...(value === null
          ? { "aria-hidden": true }
          : {
              role: "meter",
              "aria-valuemin": 0,
              "aria-valuemax": 100,
              "aria-valuenow": Math.round(value * 100),
              "aria-label": label,
            })}
        className="h-1.5 w-16 overflow-hidden rounded-full bg-primary/15"
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
