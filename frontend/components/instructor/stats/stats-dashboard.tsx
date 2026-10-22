"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ArrowLeft, Award, BarChart3, ChevronRight, Plus } from "lucide-react";
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
import { ExportButton } from "@/components/ui/export-button";
import { apiErrorMessage } from "@/lib/api/error-messages";
import {
  getInstructorInsights,
  getInstructorOverview,
  getMyTier,
  instructorExportPath,
  STATS_PERIODS,
  VERDICTS,
  type InstructorInsights,
  type InstructorOverview,
  type StatsPeriod,
  type StatsPoint,
} from "@/lib/api/instructor-stats";
import { useAuth } from "@/lib/auth/auth-provider";
import { cn } from "@/lib/utils";

import { ColumnChart, type Column } from "./column-chart";
import { CourseStatsTable } from "./course-stats-table";
import {
  bucketLabel,
  bucketTick,
  formatCount,
  formatDay,
  formatMeasure,
  formatRate,
  formatRating,
} from "./format";
import { StatTile } from "./stat-tile";

/**
 * The instructor's dashboard: learners and learning, and no money.
 *
 * Since 20/10/2026 revenue is the admin's. What an instructor sees is who
 * joined, who is active, how far they get, how they do on quizzes and code,
 * what they think, and what they ask -- each against the period before, and
 * course against course. Changing the period keeps the previous numbers on
 * screen, dimmed, until the new ones arrive.
 */
export function StatsDashboard() {
  const { accessToken } = useAuth();
  const [period, setPeriod] = useState<StatsPeriod>("30d");
  const choice = STATS_PERIODS.find((option) => option.value === period)!;

  const overview = useQuery({
    queryKey: ["instructor-stats", "overview", period],
    queryFn: () => getInstructorOverview(accessToken as string, period),
    enabled: accessToken !== null,
    placeholderData: keepPreviousData,
  });
  const insights = useQuery({
    queryKey: ["instructor-stats", "insights", period],
    queryFn: () => getInstructorInsights(accessToken as string, period),
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
            {overview.data
              ? `${formatDay(overview.data.start)} – ${formatDay(overview.data.end)} · giờ Việt Nam`
              : "Học viên, mức độ học và phản hồi của các khóa học bạn dạy."}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <PeriodPicker value={period} onChange={setPeriod} />
          <ExportButton
            path={instructorExportPath(period)}
            filename="devpath_thong-ke-giang-day.xlsx"
          />
        </div>
      </div>

      <TierSummary />

      {overview.isPending ? (
        <Skeleton />
      ) : overview.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(overview.error)}</AlertDescription>
        </Alert>
      ) : overview.data.courses_total === 0 && overview.data.students_total === 0 ? (
        <EmptyState />
      ) : (
        <div className={cn("space-y-6 transition-opacity", overview.isFetching && "opacity-60")}>
          <Overview data={overview.data} previousLabel={choice.previous} />
          {insights.data ? (
            <Insights data={insights.data} overview={overview.data} periodLabel={choice.label} />
          ) : insights.isError ? (
            <Alert variant="destructive">
              <AlertDescription>{apiErrorMessage(insights.error)}</AlertDescription>
            </Alert>
          ) : (
            <div className="h-64 animate-pulse rounded-lg border bg-muted/40" />
          )}
          <Card>
            <CardHeader>
              <CardTitle>Theo từng khóa học</CardTitle>
              <CardDescription>
                Học viên, hoàn thành, tiến độ và kết quả học tập tính từ trước tới nay; ghi danh
                mới tính trong {choice.label} gần nhất. Bấm “Theo bài” để xem học viên dừng ở đâu.
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

/** The instructor's tier in one line, with the way to the details. */
function TierSummary() {
  const { accessToken } = useAuth();
  const tier = useQuery({
    queryKey: ["instructor-tier"],
    queryFn: () => getMyTier(accessToken as string),
    enabled: accessToken !== null,
  });
  if (!tier.data) return null;
  const { current, next, eligible } = tier.data;
  return (
    <Link
      href="/giang-day/cap-bac"
      className="flex flex-wrap items-center justify-between gap-3 rounded-lg border bg-card p-4 transition-colors hover:bg-muted/40 focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
    >
      <span className="flex items-center gap-3">
        <span className="flex size-10 items-center justify-center rounded-md bg-primary/10 text-primary">
          <Award className="size-5" aria-hidden />
        </span>
        <span>
          <span className="block text-sm text-muted-foreground">Cấp giảng viên</span>
          <span className="font-semibold">
            {current.name} · nhận {formatRate(Number(current.share_rate))} mỗi lượt bán
          </span>
        </span>
      </span>
      <span className="flex items-center gap-1 text-sm text-muted-foreground">
        {next === null
          ? "Bạn đang ở cấp cao nhất"
          : eligible
            ? `Đã đủ điều kiện để được xét lên “${next.tier.name}”`
            : `${next.criteria.filter((c) => c.met).length}/${next.criteria.length} tiêu chí lên “${next.tier.name}”`}
        <ChevronRight className="size-4" aria-hidden />
      </span>
    </Link>
  );
}

const SERIES: {
  key: keyof Omit<StatsPoint, "bucket">;
  label: string;
  unit: string;
  note: string;
}[] = [
  {
    key: "new_students",
    label: "Học viên mới",
    unit: "học viên mới",
    note: "Người lần đầu ghi danh một khóa của bạn — học hai khóa vẫn tính là một.",
  },
  {
    key: "active_learners",
    label: "Học viên hoạt động",
    unit: "học viên hoạt động",
    note: "Người có học, làm quiz, nộp code, hỏi đáp hoặc ghi chú trong khóa của bạn.",
  },
  {
    key: "enrollments",
    label: "Ghi danh",
    unit: "lượt ghi danh",
    note: "Mọi lượt ghi danh mới vào các khóa của bạn.",
  },
  {
    key: "lessons_completed",
    label: "Bài hoàn thành",
    unit: "bài hoàn thành",
    note: "Số bài học được học viên đánh dấu hoàn thành.",
  },
];

function Overview({
  data,
  previousLabel,
}: {
  data: InstructorOverview;
  previousLabel: string;
}) {
  const [metric, setMetric] = useState(SERIES[0]);
  const unit = data.granularity === "day" ? "ngày" : "tháng";
  const { current, previous } = data;

  const columns: Column[] = data.series.map((point) => ({
    key: point.bucket,
    tick: bucketTick(point.bucket, data.granularity),
    label: bucketLabel(point.bucket, data.granularity),
    value: point[metric.key],
    display: `${formatCount(point[metric.key])} ${metric.unit}`,
    detail: `${formatCount(point.enrollments)} ghi danh · ${formatCount(point.completions)} hoàn thành khóa`,
  }));

  const tiles: { label: string; key: keyof Omit<typeof current, "review_avg">; note?: string }[] = [
    { label: "Học viên mới", key: "new_students", note: `${formatCount(current.enrollments)} lượt ghi danh` },
    { label: "Học viên hoạt động", key: "active_learners" },
    { label: "Bài học hoàn thành", key: "lessons_completed" },
    { label: "Lượt hoàn thành khóa", key: "completions" },
    { label: "Ghi danh mới", key: "enrollments" },
    {
      label: "Đánh giá mới",
      key: "reviews",
      note: current.review_avg === null ? undefined : `Trung bình ${formatRating(current.review_avg)}`,
    },
    { label: "Câu hỏi mới", key: "questions" },
    { label: "Thêm vào yêu thích", key: "wishlist_adds" },
  ];

  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {tiles.map((tile) => (
          <StatTile
            key={tile.key}
            label={tile.label}
            value={formatCount(current[tile.key])}
            current={current[tile.key]}
            previous={previous[tile.key]}
            previousLabel={previousLabel}
            previousDisplay={formatCount(previous[tile.key])}
            note={tile.note}
          />
        ))}
      </div>

      <p className="text-sm text-muted-foreground">
        Từ trước tới nay: {formatCount(data.students_total)} học viên ·{" "}
        {formatCount(data.enrollments_total)} lượt ghi danh · {formatCount(data.courses_published)}/
        {formatCount(data.courses_total)} khóa đang bán · {formatCount(data.certificates_total)} chứng
        chỉ đã cấp · điểm đánh giá {formatRating(data.rating_avg)} ({formatCount(data.rating_count)}{" "}
        đánh giá) · {formatCount(data.open_questions)} câu hỏi đang chờ bạn.
      </p>

      <Card>
        <CardHeader className="gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <CardTitle>
              {metric.label} theo {unit}
            </CardTitle>
            <CardDescription>{metric.note}</CardDescription>
          </div>
          <div role="group" aria-label="Chỉ số trên biểu đồ" className="flex flex-wrap gap-1">
            {SERIES.map((option) => (
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
            formatTick={formatCount}
            integer
            label={`${metric.label} theo ${unit}`}
            emptyNote="Chưa có số liệu trong kỳ này."
          />
        </CardContent>
      </Card>
    </>
  );
}

function Figure({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b py-2 text-sm last:border-0">
      <dt className="text-muted-foreground">
        {label}
        {hint ? <span className="block text-xs">{hint}</span> : null}
      </dt>
      <dd className="shrink-0 font-medium tabular-nums">{value}</dd>
    </div>
  );
}

function Bars({ rows }: { rows: { label: string; value: number }[] }) {
  const max = Math.max(1, ...rows.map((row) => row.value));
  return (
    <ul className="space-y-1.5">
      {rows.map((row) => (
        <li key={row.label} className="flex items-center gap-2 text-xs">
          <span className="w-10 shrink-0 text-muted-foreground">{row.label}</span>
          <span className="h-2 flex-1 overflow-hidden rounded-full bg-primary/10">
            <span
              className="block h-full rounded-full bg-primary"
              style={{ width: `${(row.value / max) * 100}%` }}
            />
          </span>
          <span className="w-8 shrink-0 text-right tabular-nums">{formatCount(row.value)}</span>
        </li>
      ))}
    </ul>
  );
}

function Insights({
  data,
  overview,
  periodLabel,
}: {
  data: InstructorInsights;
  overview: InstructorOverview;
  periodLabel: string;
}) {
  const { learning, quiz, code, reviews, qa, interest } = data;
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      <Card>
        <CardHeader>
          <CardTitle>Mức độ học</CardTitle>
          <CardDescription>Tính từ trước tới nay, trên mọi lượt ghi danh.</CardDescription>
        </CardHeader>
        <CardContent>
          <dl>
            <Figure label="Bắt đầu học" value={formatRate(learning.started_rate)} hint="Đã mở ít nhất một bài" />
            <Figure label="Hoàn thành khóa" value={formatRate(overview.completion_rate)} />
            <Figure label="Tiến độ trung bình" value={formatRate(overview.avg_progress)} />
            <Figure
              label="Bỏ dở"
              value={formatRate(learning.idle_rate)}
              hint="Chưa xong và 30 ngày không học"
            />
            <Figure
              label="Tới bài đầu tiên (trung vị)"
              value={formatMeasure(learning.median_days_to_first_lesson, "ngày")}
            />
            <Figure
              label="Hoàn thành khóa sau (trung vị)"
              value={formatMeasure(learning.median_days_to_complete, "ngày")}
            />
          </dl>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Quiz</CardTitle>
          <CardDescription>Bài nộp trong {periodLabel} gần nhất.</CardDescription>
        </CardHeader>
        <CardContent>
          <dl>
            <Figure label="Lượt nộp" value={formatCount(quiz.attempts)} />
            <Figure label="Số người làm" value={formatCount(quiz.learners)} />
            <Figure label="Điểm trung vị" value={formatMeasure(quiz.median_score, "/ 100")} />
            <Figure
              label="Đạt ngay lần đầu"
              value={formatRate(quiz.first_try_pass_rate)}
              hint="Lần nộp đầu tiên của mỗi người đạt điểm qua"
            />
            <Figure label="Hết giờ" value={formatRate(quiz.expired_rate)} />
          </dl>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Bài tập code</CardTitle>
          <CardDescription>Bài nộp chấm thật trong {periodLabel} gần nhất (không tính chạy thử).</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <dl>
            <Figure label="Lượt nộp" value={formatCount(code.submissions)} />
            <Figure
              label="Giải được"
              value={formatRate(code.solve_rate)}
              hint="Người nộp có ít nhất một AC trên test ẩn"
            />
            <Figure
              label="Số lần nộp tới AC (trung vị)"
              value={formatMeasure(code.median_attempts_to_ac, "lần")}
            />
          </dl>
          <Bars rows={VERDICTS.map((verdict) => ({ label: verdict, value: code.verdicts[verdict] }))} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Đánh giá</CardTitle>
          <CardDescription>
            {formatCount(reviews.new_reviews)} đánh giá mới trong {periodLabel}
            {reviews.new_review_avg !== null ? `, trung bình ${formatRating(reviews.new_review_avg)}` : ""}.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <Bars
            rows={[5, 4, 3, 2, 1].map((stars) => ({
              label: `${stars} ★`,
              value: reviews.distribution[String(stars)] ?? 0,
            }))}
          />
          <dl>
            <Figure label="Có viết nhận xét" value={formatRate(reviews.commented_rate)} />
          </dl>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Hỏi đáp</CardTitle>
          <CardDescription>Câu hỏi của học viên trong {periodLabel} gần nhất.</CardDescription>
        </CardHeader>
        <CardContent>
          <dl>
            <Figure label="Câu hỏi mới" value={formatCount(qa.questions)} />
            <Figure label="Bạn đã trả lời" value={formatRate(qa.answered_rate)} />
            <Figure
              label="Thời gian phản hồi (trung vị)"
              value={formatMeasure(qa.median_first_response_hours, "giờ")}
            />
            <Figure label="Trả lời trong 24 giờ" value={formatRate(qa.answered_within_24h_rate)} />
            <Figure label="Đã giải quyết" value={formatRate(qa.resolved_rate)} />
            <Figure label="Đang chờ bạn (tất cả)" value={formatCount(qa.backlog)} />
          </dl>
          {qa.backlog > 0 ? (
            <Button asChild variant="link" className="mt-1 h-auto px-0">
              <Link href="/giang-day/hoi-dap">Trả lời câu hỏi đang chờ</Link>
            </Button>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Mức độ quan tâm</CardTitle>
          <CardDescription>Người để ý tới khóa học của bạn.</CardDescription>
        </CardHeader>
        <CardContent>
          <dl>
            <Figure label={`Thêm vào yêu thích (${periodLabel})`} value={formatCount(interest.wishlist_adds)} />
            <Figure label="Đang trong danh sách yêu thích" value={formatCount(interest.wishlisted_now)} />
            <Figure
              label="Yêu thích → ghi danh"
              value={formatRate(interest.wishlist_conversion_rate)}
              hint="Người thêm vào yêu thích rồi ghi danh khóa đó"
            />
            <Figure label="Đang nằm trong giỏ hàng" value={formatCount(interest.in_carts_now)} />
          </dl>
        </CardContent>
      </Card>
    </div>
  );
}

export function PeriodPicker({
  value,
  onChange,
}: {
  value: StatsPeriod;
  onChange: (period: StatsPeriod) => void;
}) {
  return (
    <div role="group" aria-label="Khoảng thời gian" className="inline-flex rounded-md border p-0.5">
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
        {[0, 1, 2, 3, 4, 5, 6, 7].map((tile) => (
          <div key={tile} className="h-24 animate-pulse rounded-lg border bg-muted/40" />
        ))}
      </div>
      <div className="h-72 animate-pulse rounded-lg border bg-muted/40" />
    </div>
  );
}

function EmptyState() {
  return (
    <Card>
      <CardHeader>
        <div className="mb-2 flex size-10 items-center justify-center rounded-md bg-muted">
          <BarChart3 className="size-5 text-muted-foreground" aria-hidden />
        </div>
        <CardTitle>Chưa có gì để thống kê</CardTitle>
        <CardDescription>
          Số liệu xuất hiện ở đây khi khóa học đầu tiên của bạn có người ghi danh.
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
