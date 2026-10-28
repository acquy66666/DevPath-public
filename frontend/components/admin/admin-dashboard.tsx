"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";

import Link from "next/link";
import { useState } from "react";

import { ADMIN_KEY, useAdminSummary } from "@/components/admin/admin-nav";
import { AdminTitle, EmptyState, ListSkeleton } from "@/components/admin/admin-shared";
import { CourseStatusBadge } from "@/components/instructor/course-status-badge";
import { ColumnChart, type Column } from "@/components/instructor/stats/column-chart";
import {
  bucketLabel,
  bucketTick,
  formatCompact,
  formatCount,
  formatDay,
} from "@/components/instructor/stats/format";
import { StatTile } from "@/components/instructor/stats/stat-tile";
import { PeriodPicker } from "@/components/instructor/stats/stats-dashboard";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { ExportButton } from "@/components/ui/export-button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { attentionCards, waitedDays } from "@/lib/admin/admin-view";
import {
  getPlatformOverview,
  listAdminCourses,
  listHotCourses,
  type HotCourse,
  type PlatformOverview,
} from "@/lib/api/admin";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { overviewExportPath } from "@/lib/api/finance";
import { STATS_PERIODS, type StatsPeriod } from "@/lib/api/instructor-stats";
import { useAuth } from "@/lib/auth/auth-provider";
import { formatAmount } from "@/lib/format";
import { cn } from "@/lib/utils";

const DECIMAL = new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 1 });

/**
 * The whole platform at a glance: money in, people active, courses joined.
 *
 * Built from the instructor dashboard's parts (tiles, column chart, period
 * picker) so the two read the same way; the difference is scope, and the
 * active-user figures only an admin gets.
 */
export function AdminDashboard() {
  const { accessToken } = useAuth();
  const [period, setPeriod] = useState<StatsPeriod>("30d");
  const choice = STATS_PERIODS.find((option) => option.value === period)!;

  const overview = useQuery({
    queryKey: [...ADMIN_KEY, "stats", "overview", period],
    queryFn: () => getPlatformOverview(accessToken as string, period),
    enabled: accessToken !== null,
    placeholderData: keepPreviousData,
  });

  return (
    <>
      <AdminTitle title="Tổng quan" description="Việc đang chờ bạn quyết định, rồi số liệu toàn sàn." />
      <Attention />
    <section className="space-y-6" aria-labelledby="admin-overview-title">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 id="admin-overview-title" className="text-h3">
            Toàn sàn
          </h2>
          <p className="text-sm text-muted-foreground">
            {overview.data
              ? `${formatDay(overview.data.start)} – ${formatDay(overview.data.end)} · giờ Việt Nam`
              : "Doanh thu, người dùng hoạt động và khóa học hot."}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <PeriodPicker value={period} onChange={setPeriod} />
          <ExportButton path={overviewExportPath(period)} filename="devpath_tong-quan.xlsx" />
        </div>
      </div>

      {overview.isPending ? (
        <ListSkeleton rows={2} height="h-40" fill />
      ) : overview.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(overview.error)}</AlertDescription>
        </Alert>
      ) : (
        <div className={cn("space-y-6 transition-opacity", overview.isFetching && "opacity-60")}>
          <Overview data={overview.data} previousLabel={choice.previous} />
        </div>
      )}

      <HotCourses period={period} periodLabel={choice.label} />
    </section>
    </>
  );
}

/**
 * What waits for the admin, above the numbers: the reason most visits to
 * this page happen. The oldest course is the head of the review queue, which
 * the backend sorts longest-waiting first.
 */
function Attention() {
  const { accessToken } = useAuth();
  const summary = useAdminSummary();
  const waiting = (summary.data?.pending_courses ?? 0) > 0;
  const head = useQuery({
    queryKey: [...ADMIN_KEY, "courses", "pending_review", "", 1],
    queryFn: () => listAdminCourses(accessToken as string, { status: "pending_review", q: "", page: 1 }),
    enabled: accessToken !== null && waiting,
  });
  const oldest = head.data?.items[0];

  return (
    <section className="space-y-3" aria-labelledby="admin-attention-title">
      <h2 id="admin-attention-title" className="text-h3">
        Cần xử lý
      </h2>
      {summary.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(summary.error)}</AlertDescription>
        </Alert>
      ) : summary.data ? (
        <ul className="grid gap-3 sm:grid-cols-3 sm:gap-4">
          {attentionCards(
            summary.data,
            oldest ? { title: oldest.title, days: waitedDays(oldest.updated_at, new Date()) } : null,
          ).map((card) => (
            <li key={card.kind}>
              <Link
                href={card.href}
                className={cn(
                  "flex h-full flex-col gap-1 rounded-lg border p-4 transition-colors duration-fast sm:p-5",
                  card.quiet ? "bg-muted hover:bg-accent" : "bg-card hover:border-primary",
                )}
              >
                <span className="text-body-sm text-muted-foreground">{card.label}</span>
                <span className="text-h1 tabular-nums">{formatCount(card.count)}</span>
                <span className="text-body-sm text-pretty">{card.detail}</span>
                <span className="mt-auto pt-2 text-body-sm font-semibold text-link">
                  {card.action} <span aria-hidden>→</span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <div className="grid gap-3 sm:grid-cols-3 sm:gap-4" aria-hidden>
          {[0, 1, 2].map((tile) => (
            <Skeleton key={tile} className="h-36 rounded-lg sm:h-40" />
          ))}
        </div>
      )}
    </section>
  );
}

function Overview({ data, previousLabel }: { data: PlatformOverview; previousLabel: string }) {
  const unit = data.granularity === "day" ? "ngày" : "tháng";

  const revenue: Column[] = data.series.map((point) => ({
    key: point.bucket,
    tick: bucketTick(point.bucket, data.granularity),
    label: bucketLabel(point.bucket, data.granularity),
    value: Number(point.revenue),
    display: formatAmount(point.revenue),
    detail: `${formatCount(point.orders)} đơn hàng`,
  }));

  const active: Column[] = data.series.map((point) => ({
    key: point.bucket,
    tick: bucketTick(point.bucket, data.granularity),
    label: bucketLabel(point.bucket, data.granularity),
    value: point.active_users,
    display: `${formatCount(point.active_users)} người hoạt động`,
    detail: `${formatCount(point.new_users)} tài khoản mới · ${formatCount(point.enrollments)} lượt ghi danh`,
  }));

  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile
          label="Doanh thu sàn"
          value={formatAmount(data.current.revenue)}
          current={Number(data.current.revenue)}
          previous={Number(data.previous.revenue)}
          previousLabel={previousLabel}
          previousDisplay={formatAmount(data.previous.revenue)}
          note={`${formatCount(data.current.orders)} đơn đã thanh toán`}
        />
        <StatTile
          label="DAU trung bình"
          value={DECIMAL.format(data.current.avg_daily_active)}
          current={data.current.avg_daily_active}
          previous={data.previous.avg_daily_active}
          previousLabel={previousLabel}
          previousDisplay={DECIMAL.format(data.previous.avg_daily_active)}
          note={`Hôm nay: ${formatCount(data.active_today)} người`}
        />
        <StatTile
          label="Người dùng hoạt động"
          value={formatCount(data.current.active_users)}
          current={data.current.active_users}
          previous={data.previous.active_users}
          previousLabel={previousLabel}
          previousDisplay={formatCount(data.previous.active_users)}
          note="Khác nhau, trong cả kỳ"
        />
        <StatTile
          label="Tài khoản mới"
          value={formatCount(data.current.new_users)}
          current={data.current.new_users}
          previous={data.previous.new_users}
          previousLabel={previousLabel}
          previousDisplay={formatCount(data.previous.new_users)}
          note={`${formatCount(data.current.enrollments)} lượt ghi danh`}
        />
      </div>

      <p className="text-sm text-muted-foreground">
        Từ trước tới nay:{" "}
        <span className="text-foreground">{formatAmount(data.revenue_all_time)}</span> doanh thu ·{" "}
        {formatCount(data.users_total)} tài khoản · {formatCount(data.courses_published)} khóa
        đang bán · {formatCount(data.enrollments_total)} lượt ghi danh. Doanh thu là số tiền người
        mua thực trả (sau mã giảm giá), chưa chia cho giảng viên.
      </p>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Doanh thu theo {unit}</CardTitle>
            <CardDescription>Theo lúc cổng thanh toán xác nhận đã nhận tiền.</CardDescription>
          </CardHeader>
          <CardContent>
            <ColumnChart
              columns={revenue}
              formatTick={formatCompact}
              label={`Doanh thu sàn theo ${unit}`}
              emptyNote="Chưa có đơn hàng nào được thanh toán trong kỳ này."
            />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>{data.granularity === "day" ? "DAU" : "Người hoạt động theo tháng"}</CardTitle>
            <CardDescription>
              Người có ít nhất một hoạt động được ghi lại: đăng nhập hoặc mở lại phiên, học bài,
              làm quiz, nộp code, hỏi trợ giảng AI, hỏi đáp, ghi chú, đặt hàng, ghi danh.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ColumnChart
              columns={active}
              formatTick={formatCount}
              integer
              label={`Người dùng hoạt động theo ${unit}`}
              emptyNote="Chưa có ai hoạt động trong kỳ này."
            />
          </CardContent>
        </Card>
      </div>
    </>
  );
}

function HotCourses({ period, periodLabel }: { period: StatsPeriod; periodLabel: string }) {
  const { accessToken } = useAuth();
  const hot = useQuery({
    queryKey: [...ADMIN_KEY, "stats", "hot", period],
    queryFn: () => listHotCourses(accessToken as string, period),
    enabled: accessToken !== null,
    placeholderData: keepPreviousData,
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Khóa học hot</CardTitle>
        <CardDescription>
          Nhiều lượt ghi danh mới nhất trong {periodLabel} gần nhất; bằng nhau thì xét doanh thu.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {hot.isError ? (
          <Alert variant="destructive">
            <AlertDescription>{apiErrorMessage(hot.error)}</AlertDescription>
          </Alert>
        ) : hot.isPending ? (
          <ListSkeleton rows={3} height="h-12" />
        ) : hot.data.items.length === 0 ? (
          <EmptyState
            mood="empty-courses"
            title="Chưa có lượt ghi danh nào trong kỳ này"
            hint="Chọn khoảng thời gian dài hơn để xem khóa học nào đang thu hút học viên."
          />
        ) : (
          <div className={cn("-mx-4 overflow-x-auto px-4", hot.isPlaceholderData && "opacity-60")}>
            <table className="w-full min-w-[36rem] text-sm">
              <thead>
                <tr className="border-b text-left text-muted-foreground">
                  <th scope="col" className="w-8 py-2 pr-2 font-normal">
                    #
                  </th>
                  <th scope="col" className="py-2 pr-3 font-normal">
                    Khóa học
                  </th>
                  <th scope="col" className="py-2 pr-3 text-right font-normal">
                    Ghi danh mới
                  </th>
                  <th scope="col" className="py-2 pr-3 text-right font-normal">
                    Lượt bán
                  </th>
                  <th scope="col" className="py-2 text-right font-normal">
                    Doanh thu
                  </th>
                </tr>
              </thead>
              <tbody>
                {hot.data.items.map((course, index) => (
                  <HotRow key={course.id} course={course} rank={index + 1} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function HotRow({ course, rank }: { course: HotCourse; rank: number }) {
  const href =
    course.status === "published" && !course.is_deleted
      ? `/khoa-hoc/${course.slug}`
      : `/quan-tri/khoa-hoc/${course.id}`;
  return (
    <tr className="border-b last:border-b-0">
      <td className="py-2 pr-2 text-muted-foreground tabular-nums">{rank}</td>
      <td className="py-2 pr-3">
        <Link href={href} className="font-medium hover:underline">
          {course.title}
        </Link>
        <span className="mt-0.5 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          {course.instructor_name} · {formatCount(course.students_count)} học viên ·{" "}
          {/* Ratings run 1–5, so an average of 0 means nobody has rated yet. */}
          {Number(course.rating_avg) > 0 ? `★ ${DECIMAL.format(Number(course.rating_avg))}` : "chưa có đánh giá"}
          {course.status !== "published" || course.is_deleted ? (
            <CourseStatusBadge status={course.status} />
          ) : null}
        </span>
      </td>
      <td className="py-2 pr-3 text-right tabular-nums">{formatCount(course.new_enrollments)}</td>
      <td className="py-2 pr-3 text-right tabular-nums">{formatCount(course.sales)}</td>
      <td className="py-2 text-right tabular-nums">{formatAmount(course.revenue)}</td>
    </tr>
  );
}
