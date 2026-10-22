"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ArrowDownRight, ArrowUpRight } from "lucide-react";
import { useState } from "react";

import { ADMIN_KEY } from "@/components/admin/admin-nav";
import { ListSkeleton } from "@/components/admin/admin-shared";
import { formatCount, formatMeasure, formatRate, formatRating } from "@/components/instructor/stats/format";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ExportButton } from "@/components/ui/export-button";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { getRankings, rankingsPath, type RankEntry, type Ranking, type RankUnit } from "@/lib/api/finance";
import { useAuth } from "@/lib/auth/auth-provider";
import { cn } from "@/lib/utils";

import { addDays, DateRangePicker, day, money, vietnamToday, type DateRange } from "./finance-shared";

const GROUPS: { value: Ranking["group"]; label: string }[] = [
  { value: "instructors", label: "Giảng viên" },
  { value: "courses", label: "Khóa học" },
  { value: "coupons", label: "Mã giảm giá" },
  { value: "categories", label: "Danh mục" },
];

function show(value: RankEntry["value"] | null, unit: RankUnit): string {
  if (value === null) return "—";
  const number = Number(value);
  switch (unit) {
    case "money":
      return money(String(value));
    case "rating":
      return formatRating(number);
    case "rate":
      return formatRate(number);
    case "hours":
      return formatMeasure(number, "giờ");
    default:
      return formatCount(number);
  }
}

/**
 * One leaderboard per measure, over one date range, each with what the same
 * entry did in the range just before. Ties share a rank, as in a race.
 */
export function RankingsPage() {
  const { accessToken } = useAuth();
  const today = vietnamToday();
  const [range, setRange] = useState<DateRange>({ start: addDays(today, -29), end: today });
  const [group, setGroup] = useState<Ranking["group"]>("instructors");

  const query = useQuery({
    queryKey: [...ADMIN_KEY, "finance", "rankings", range],
    queryFn: () => getRankings(accessToken as string, range),
    enabled: accessToken !== null,
    placeholderData: keepPreviousData,
  });

  return (
    <section className="space-y-6" aria-labelledby="rankings-title">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 id="rankings-title" className="font-semibold">
            Bảng xếp hạng
          </h2>
          <p className="text-sm text-muted-foreground">
            Mỗi khoản mục một bảng. Đồng hạng kiểu thi đấu (1, 2, 2, 4); cột cuối là kỳ ngay trước.
          </p>
        </div>
        <ExportButton path={rankingsPath(range, "/export.xlsx")} filename="devpath_xep-hang.xlsx" />
      </div>

      <div className="rounded-lg border p-4">
        <DateRangePicker value={range} onChange={setRange} />
      </div>

      <div role="tablist" aria-label="Nhóm xếp hạng" className="flex flex-wrap gap-1 border-b">
        {GROUPS.map((option) => (
          <button
            key={option.value}
            role="tab"
            type="button"
            aria-selected={option.value === group}
            onClick={() => setGroup(option.value)}
            className={cn(
              "-mb-px border-b-2 px-3 py-2 text-sm transition-colors focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none",
              option.value === group
                ? "border-primary font-medium"
                : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            {option.label}
          </button>
        ))}
      </div>

      {query.isPending ? (
        <ListSkeleton rows={3} height="h-48" />
      ) : query.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(query.error)}</AlertDescription>
        </Alert>
      ) : (
        <div className={cn("space-y-4 transition-opacity", query.isFetching && "opacity-60")}>
          {group === "instructors" ? (
            <p className="text-sm text-muted-foreground">
              Độ tập trung doanh thu: giảng viên số 1 chiếm{" "}
              <strong className="text-foreground">{formatRate(query.data.concentration.top1)}</strong>, 5
              người đầu {formatRate(query.data.concentration.top5)}, 10 người đầu{" "}
              {formatRate(query.data.concentration.top10)} (trên{" "}
              {formatCount(query.data.concentration.instructors)} giảng viên có bán trong kỳ).
            </p>
          ) : null}
          <div className="grid gap-4 lg:grid-cols-2">
            {query.data.rankings
              .filter((ranking) => ranking.group === group)
              .map((ranking) => (
                <RankingCard
                  key={ranking.code}
                  ranking={ranking}
                  previousLabel={`${day(query.data.previous_start)} – ${day(query.data.previous_end)}`}
                />
              ))}
          </div>
        </div>
      )}
    </section>
  );
}

function RankingCard({ ranking, previousLabel }: { ranking: Ranking; previousLabel: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{ranking.title}</CardTitle>
        <CardDescription>
          {ranking.note ?? `So với ${previousLabel}.`}
          {ranking.total_entries > ranking.entries.length
            ? ` Hiện ${ranking.entries.length}/${ranking.total_entries} — đủ cả trong tệp Excel.`
            : ""}
        </CardDescription>
      </CardHeader>
      <CardContent>
        {ranking.entries.length === 0 ? (
          <p className="py-4 text-center text-sm text-muted-foreground">Chưa có ai trong bảng này.</p>
        ) : (
          <ol className="divide-y">
            {ranking.entries.map((entry) => {
              const now = Number(entry.value);
              const before = entry.previous === null ? null : Number(entry.previous);
              const better =
                before === null ? null : ranking.ascending ? now < before : now > before;
              return (
                <li key={entry.key} className="flex items-center gap-3 py-2 text-sm">
                  <span
                    className={cn(
                      "flex size-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold tabular-nums",
                      entry.rank === 1 ? "bg-primary text-primary-foreground" : "bg-muted",
                    )}
                  >
                    {entry.rank}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium">{entry.label}</span>
                    {entry.detail ? (
                      <span className="block truncate text-xs text-muted-foreground">
                        {entry.detail}
                      </span>
                    ) : null}
                  </span>
                  <span className="shrink-0 text-right tabular-nums">
                    {show(entry.value, ranking.unit)}
                    {before !== null ? (
                      <span
                        className={cn(
                          "flex items-center justify-end gap-0.5 text-xs",
                          better === true && "text-emerald-700 dark:text-emerald-400",
                          better === false && now !== before && "text-red-700 dark:text-red-400",
                          now === before && "text-muted-foreground",
                        )}
                      >
                        {now !== before ? (
                          better ? (
                            <ArrowUpRight className="size-3" aria-hidden />
                          ) : (
                            <ArrowDownRight className="size-3" aria-hidden />
                          )
                        ) : null}
                        kỳ trước {show(entry.previous, ranking.unit)}
                      </span>
                    ) : null}
                  </span>
                </li>
              );
            })}
          </ol>
        )}
      </CardContent>
    </Card>
  );
}
