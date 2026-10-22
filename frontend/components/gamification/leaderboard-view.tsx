"use client";

import { useQuery } from "@tanstack/react-query";
import { Medal } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { UserAvatar } from "@/components/auth/user-avatar";
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
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton, SkeletonRegion, SkeletonText } from "@/components/ui/skeleton";
import { apiErrorMessage } from "@/lib/api/error-messages";
import {
  getLeaderboard,
  type Leaderboard,
  type LeaderboardPeriod,
} from "@/lib/api/leaderboard";
import { useAuth } from "@/lib/auth/auth-provider";
import { cn } from "@/lib/utils";

const PERIODS: { value: LeaderboardPeriod; tab: string; phrase: string }[] = [
  { value: "week", tab: "Tuần này", phrase: "tuần này" },
  { value: "month", tab: "Tháng này", phrase: "tháng này" },
  { value: "all", tab: "Mọi thời gian", phrase: "từ trước tới nay" },
];

/** Gold, silver, bronze -- with the number beside them, never colour alone. */
const MEDALS = ["text-amber-500", "text-slate-400", "text-orange-700"];

/** "2026-09-28" → "28/09". A date, not an instant: no time zone to get wrong. */
function dayMonth(iso: string): string {
  const [, month, day] = iso.split("-");
  return `${day}/${month}`;
}

function periodCaption(board: Leaderboard): string {
  if (board.period === "week" && board.starts_on && board.ends_on) {
    return `Từ thứ Hai ${dayMonth(board.starts_on)} đến Chủ nhật ${dayMonth(board.ends_on)}`;
  }
  if (board.period === "month" && board.starts_on) {
    const [year, month] = board.starts_on.split("-");
    return `Tháng ${Number(month)}/${year}`;
  }
  return "Tính cả mọi XP từ trước tới nay";
}

/**
 * The leaderboard: three periods, one page at a time, and where you stand.
 *
 * Guarded here like "Khóa học của tôi": the API answers 401 without a token,
 * whatever this draws. Your own rank is shown above the list whether or not
 * you are on the page being read -- the question most readers came with.
 */
export function LeaderboardView() {
  const { accessToken, status } = useAuth();
  const [period, setPeriod] = useState<LeaderboardPeriod>("week");
  const [page, setPage] = useState(1);

  const query = useQuery({
    queryKey: ["leaderboard", period, page],
    queryFn: () => getLeaderboard(accessToken as string, period, page),
    enabled: status === "authenticated" && accessToken !== null,
    staleTime: 30_000,
    // Turning a page keeps the old rows up until the new ones arrive, rather
    // than collapsing the list to a skeleton and back. Switching period does
    // not: last week's names under "Tháng này" would be a wrong answer.
    placeholderData: (previous) => (previous?.period === period ? previous : undefined),
  });

  if (status === "anonymous") {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Đăng nhập để xem bảng xếp hạng</CardTitle>
          <CardDescription>
            Bảng xếp hạng chỉ hiển thị cho học viên đã đăng nhập.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button asChild>
            <Link href="/dang-nhap?next=/bang-xep-hang">Đăng nhập</Link>
          </Button>
        </CardContent>
      </Card>
    );
  }

  const phrase = PERIODS.find((item) => item.value === period)?.phrase ?? "";
  const board = query.data;

  return (
    <div className="space-y-5">
      <Tabs
        value={period}
        onValueChange={(value) => {
          setPeriod(value as LeaderboardPeriod);
          setPage(1);
        }}
      >
        <TabsList className="w-full">
          {PERIODS.map((item) => (
            <TabsTrigger key={item.value} value={item.value}>
              {item.tab}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {query.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(query.error)}</AlertDescription>
        </Alert>
      ) : !board ? (
        // The "you" card and the board's first rows, at their real sizes.
        <SkeletonRegion label="Đang tải bảng xếp hạng…" className="space-y-4">
          <div className="rounded-lg border bg-card p-4">
            <SkeletonText size="caption" className="h-4 w-40" />
            <SkeletonText size="h3" className="mt-1 w-72 max-w-full" />
          </div>
          <ol className="divide-y rounded-lg border bg-card" aria-hidden>
            {[0, 1, 2, 3, 4].map((row) => (
              <li key={row} className="flex items-center gap-3 px-4 py-3">
                <SkeletonText className="w-10 shrink-0" />
                <Skeleton className="size-9 shrink-0 rounded-full" />
                <SkeletonText className="min-w-0 flex-1" />
                <SkeletonText className="w-16 shrink-0" />
              </li>
            ))}
          </ol>
        </SkeletonRegion>
      ) : (
        <>
          <div className="rounded-lg border bg-card p-4">
            <p className="text-xs text-muted-foreground">{periodCaption(board)}</p>
            {board.me ? (
              <p className="mt-1 text-lg font-semibold">
                Bạn đang đứng hạng {board.me.rank}
                <span className="font-normal text-muted-foreground">
                  {" "}
                  / {board.total} người · {board.me.xp.toLocaleString("vi-VN")} XP{" "}
                  {phrase}
                </span>
              </p>
            ) : (
              <p className="mt-1 text-sm">
                Bạn chưa có XP {phrase}.{" "}
                <Link href="/khoa-hoc-cua-toi" className="font-medium text-primary hover:underline">
                  Hoàn thành một bài học
                </Link>{" "}
                để có tên trên bảng.
              </p>
            )}
          </div>

          {board.items.length === 0 ? (
            <EmptyState
              title={`Chưa ai có XP ${phrase}`}
              description="Người đầu tiên hoàn thành một bài học sẽ đứng đầu bảng."
            />
          ) : (
            <ol
              className={cn(
                "divide-y rounded-lg border bg-card",
                query.isPlaceholderData && "opacity-60",
              )}
              aria-label={`Bảng xếp hạng ${phrase}`}
            >
              {board.items.map((entry) => (
                <li
                  key={entry.user.id}
                  className={cn(
                    "flex items-center gap-3 px-4 py-3",
                    entry.is_me && "bg-primary/5",
                  )}
                >
                  <span className="flex w-10 shrink-0 items-center gap-1 font-semibold tabular-nums">
                    {entry.rank <= 3 ? (
                      <Medal className={cn("size-4", MEDALS[entry.rank - 1])} aria-hidden />
                    ) : null}
                    {entry.rank}
                  </span>
                  <UserAvatar user={entry.user} className="size-9 text-xs" />
                  <span className="min-w-0 flex-1 truncate font-medium">
                    {entry.user.full_name}
                    {entry.is_me ? (
                      <Badge variant="secondary" className="ml-2 align-middle">
                        Bạn
                      </Badge>
                    ) : null}
                  </span>
                  <span className="shrink-0 font-semibold tabular-nums">
                    {entry.xp.toLocaleString("vi-VN")}
                    <span className="ml-1 text-xs font-normal text-muted-foreground">XP</span>
                  </span>
                </li>
              ))}
            </ol>
          )}

          <Pager board={board} onPage={setPage} />
        </>
      )}
    </div>
  );
}

function Pager({ board, onPage }: { board: Leaderboard; onPage: (page: number) => void }) {
  const pageCount = Math.max(1, Math.ceil(board.total / board.page_size));
  if (pageCount <= 1) return null;

  return (
    <div className="flex items-center justify-center gap-3">
      <Button
        variant="outline"
        size="sm"
        disabled={board.page === 1}
        onClick={() => onPage(board.page - 1)}
      >
        Trang trước
      </Button>
      <span className="text-sm text-muted-foreground">
        Trang {board.page} / {pageCount}
      </span>
      <Button
        variant="outline"
        size="sm"
        disabled={board.page >= pageCount}
        onClick={() => onPage(board.page + 1)}
      >
        Trang sau
      </Button>
    </div>
  );
}
