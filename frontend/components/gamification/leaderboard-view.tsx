"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowUp, Crown } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { UserAvatar } from "@/components/auth/user-avatar";
import { Mascot } from "@/components/mascot/mascot";
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
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton, SkeletonRegion, SkeletonText } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { apiErrorMessage } from "@/lib/api/error-messages";
import {
  getLeaderboard,
  type Leaderboard,
  type LeaderboardEntry,
  type LeaderboardPeriod,
} from "@/lib/api/leaderboard";
import { useAuth } from "@/lib/auth/auth-provider";
import {
  PERIODS,
  formatXp,
  medalFor,
  periodCaption,
  periodPhrase,
  podiumOrder,
  rankRise,
  riseLine,
  splitPodium,
  standing,
  type Medal,
} from "@/lib/gamification/rank-view";
import { rankSeenKey, readItem, writeItem } from "@/lib/gamification/seen";
import { cn } from "@/lib/utils";

/** The step under each place, and the ring round its face: medal tokens, never colour alone. */
const MEDAL_STYLES: Record<Medal, { step: string; number: string; ring: string }> = {
  gold: { step: "h-28 border-medal-gold bg-reward-soft", number: "text-reward-foreground", ring: "ring-medal-gold" },
  silver: { step: "h-21 border-medal-silver bg-muted", number: "text-muted-foreground", ring: "ring-medal-silver" },
  bronze: { step: "h-16 border-medal-bronze bg-reward-soft/60", number: "text-streak-text", ring: "ring-medal-bronze" },
};

/**
 * The leaderboard: three periods, one page at a time, where you stand, and
 * the top three on a podium.
 *
 * Guarded here like "Khóa học của tôi": the API answers 401 without a token,
 * whatever this draws. Your own rank is shown above the list whether or not
 * you are on the page being read -- the question most readers came with.
 */
export function LeaderboardView() {
  const { accessToken, status, user } = useAuth();
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

  const board = query.data;

  return (
    <Tabs
      value={period}
      onValueChange={(value) => {
        setPeriod(value as LeaderboardPeriod);
        setPage(1);
      }}
      className="gap-5"
    >
      <TabsList className="w-full" aria-label="Khoảng thời gian">
        {PERIODS.map((item) => (
          <TabsTrigger key={item.value} value={item.value}>
            {item.tab}
          </TabsTrigger>
        ))}
      </TabsList>

      {/* Every trigger has its panel; only the chosen one holds the board. */}
      {PERIODS.map((item) => (
        <TabsContent key={item.value} value={item.value} className="flex flex-col gap-5">
          {item.value !== period ? null : query.isError ? (
            <Alert variant="destructive">
              <AlertDescription>{apiErrorMessage(query.error)}</AlertDescription>
            </Alert>
          ) : !board ? (
            <BoardSkeleton />
          ) : (
            <Board
              board={board}
              userId={user?.id ?? null}
              faded={query.isPlaceholderData}
              onPage={setPage}
            />
          )}
        </TabsContent>
      ))}
    </Tabs>
  );
}

function Board({
  board,
  userId,
  faded,
  onPage,
}: {
  board: Leaderboard;
  userId: string | null;
  faded: boolean;
  onPage: (page: number) => void;
}) {
  const phrase = periodPhrase(board.period);
  const { podium, rest } = splitPodium(board);

  return (
    <>
      <p className="text-body-sm text-muted-foreground">{periodCaption(board)}</p>

      {/* A new rank is a new card: it compares with the last visit afresh. */}
      <YouCard key={`${board.period}:${board.starts_on}:${board.me?.rank ?? "-"}`} board={board} userId={userId} />

      {board.items.length === 0 ? (
        <EmptyState
          title={`Chưa ai có XP ${phrase}`}
          description="Người đầu tiên hoàn thành một bài học sẽ đứng đầu bảng."
        />
      ) : (
        <div className={cn("flex flex-col gap-5", faded && "opacity-60")}>
          {podium.length > 0 ? <Podium podium={podium} phrase={phrase} /> : null}
          {rest.length > 0 ? (
            <ol
              aria-label={podium.length > 0 ? `Bảng xếp hạng ${phrase}, từ hạng ${rest[0].rank}` : `Bảng xếp hạng ${phrase}`}
              className="divide-y overflow-hidden rounded-lg border bg-card"
            >
              {rest.map((entry) => (
                <Row key={entry.user.id} entry={entry} />
              ))}
            </ol>
          ) : null}
        </div>
      )}

      <Pager board={board} onPage={onPage} />
    </>
  );
}

function readRank(key: string | null): number | null {
  if (key === null) return null;
  const raw = readItem("local", key);
  if (raw === null) return null;
  const value = Number(raw);
  return Number.isInteger(value) && value > 0 ? value : null;
}

/**
 * Where you stand, with Naomi on the podium. She jumps once when your rank is
 * better than the last time this browser saw this board (this week, this
 * month or all time); a first visit, or the same rank, is a still picture.
 * Not on the board this period: no Naomi -- the empty board, if it is empty,
 * has the page's one.
 */
function YouCard({ board, userId }: { board: Leaderboard; userId: string | null }) {
  const key = userId ? rankSeenKey(userId, board.period, board.starts_on) : null;
  const current = board.me?.rank ?? null;
  // Decided once per card, in the browser: the board only exists there.
  const [rise] = useState(() => rankRise(readRank(key), current));
  useEffect(() => {
    if (key !== null && current !== null) writeItem("local", key, String(current));
  }, [key, current]);

  const words = standing(board);

  if (board.me === null) {
    return (
      <section aria-label="Vị trí của bạn" className="rounded-lg border bg-card p-4">
        <p className="text-title">{words.headline}</p>
        <p className="mt-1 text-body-sm text-muted-foreground">
          <Link href="/khoa-hoc-cua-toi" className="font-semibold text-link underline-offset-4 hover:underline">
            Hoàn thành một bài học
          </Link>{" "}
          để có tên trên bảng.
        </p>
      </section>
    );
  }

  return (
    <section
      aria-label="Vị trí của bạn"
      className="flex items-center gap-3 rounded-lg border bg-card py-3 pr-4 pl-2 sm:gap-5 sm:py-4 sm:pr-6 sm:pl-4"
    >
      <Mascot mood="levelup" event={rise > 0 ? `${board.period}:${board.starts_on}:${current}` : null} className="size-20 sm:size-26" />
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        {rise > 0 ? (
          <Badge variant="streak" className="mb-0.5 h-6.5 bg-reward-soft text-reward-foreground [&>svg]:text-reward-mark">
            <ArrowUp aria-hidden />
            {riseLine(rise)}
          </Badge>
        ) : null}
        <h2 className="text-h3 text-balance">{words.headline}</h2>
        <p className="text-body-sm text-muted-foreground">{words.stats}</p>
        {words.gap ? <p className="text-body-sm text-foreground">{words.gap}</p> : null}
      </div>
    </section>
  );
}

/** Second, first, third: the first page's top three, each on a step as high as the rank. */
function Podium({ podium, phrase }: { podium: LeaderboardEntry[]; phrase: string }) {
  return (
    <section aria-label={`Ba hạng đầu ${phrase}`} className="overflow-hidden rounded-lg border bg-card px-3 pt-4 sm:px-6 sm:pt-6">
      <ol className="grid grid-cols-3 items-end gap-2 sm:gap-3">
        {podiumOrder(podium).map((entry) => {
          const medal = medalFor(entry.rank) ?? "bronze";
          const style = MEDAL_STYLES[medal];
          const first = entry.rank === 1;
          return (
            <li key={entry.user.id} className="flex min-w-0 flex-col items-center gap-1.5 text-center sm:gap-2">
              {first ? <Crown className="size-5 text-medal-gold sm:size-6" aria-hidden /> : null}
              <UserAvatar
                user={entry.user}
                className={cn(
                  "ring-2 ring-offset-2 ring-offset-card sm:ring-[3px]",
                  style.ring,
                  first ? "size-13 text-base sm:size-16 sm:text-lg" : "size-11 text-sm sm:size-14 sm:text-base",
                )}
              />
              <span className="flex min-w-0 max-w-full flex-col items-center">
                <span className="line-clamp-2 text-body-sm font-semibold sm:text-title">{entry.user.full_name}</span>
                <span className="flex flex-wrap items-center justify-center gap-1.5">
                  <span className="text-caption text-muted-foreground tabular-nums sm:text-body-sm">{formatXp(entry.xp)}</span>
                  {entry.is_me ? <Badge variant="secondary">Bạn</Badge> : null}
                </span>
              </span>
              <span
                className={cn(
                  "mt-1 flex w-full items-center justify-center rounded-t-md border-t-4 text-numeral font-bold tabular-nums",
                  style.step,
                  style.number,
                )}
              >
                <span className="sr-only">Hạng </span>
                {entry.rank}
              </span>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

function Row({ entry }: { entry: LeaderboardEntry }) {
  return (
    <li
      aria-current={entry.is_me ? "true" : undefined}
      className={cn("flex items-center gap-3 px-4 py-3 sm:px-5", entry.is_me && "bg-secondary")}
    >
      <span
        className={cn(
          "w-8 shrink-0 font-semibold tabular-nums",
          entry.is_me ? "text-secondary-foreground" : "text-muted-foreground",
        )}
      >
        <span className="sr-only">Hạng </span>
        {entry.rank}
      </span>
      <UserAvatar user={entry.user} className="size-9 text-xs" />
      <span className="flex min-w-0 flex-1 items-center gap-2">
        <span className="line-clamp-1 font-medium">{entry.user.full_name}</span>
        {entry.is_me ? (
          <Badge variant="outline" className="bg-card">
            Bạn
          </Badge>
        ) : null}
      </span>
      <span className="shrink-0 font-semibold tabular-nums">
        {entry.xp.toLocaleString("vi-VN")}
        <span className="ml-1 text-xs font-normal text-muted-foreground">XP</span>
      </span>
    </li>
  );
}

/** The "you" card, the podium and the first rows, at their real sizes. */
function BoardSkeleton() {
  return (
    <SkeletonRegion label="Đang tải bảng xếp hạng…" className="flex flex-col gap-5">
      <SkeletonText size="body-sm" className="w-72 max-w-full" />
      <div className="flex items-center gap-3 rounded-lg border bg-card py-3 pr-4 pl-2 sm:gap-5 sm:py-4 sm:pr-6 sm:pl-4">
        <span className="size-20 shrink-0 sm:size-26" />
        <div className="flex flex-1 flex-col gap-1">
          <SkeletonText size="h3" className="w-64 max-w-full" />
          <SkeletonText size="body-sm" className="w-48 max-w-full" />
          <SkeletonText size="body-sm" className="w-40 max-w-full" />
        </div>
      </div>
      <div className="grid h-60 grid-cols-3 items-end gap-2 rounded-lg border bg-card px-3 pt-4 sm:h-68 sm:gap-3 sm:px-6 sm:pt-6">
        <Skeleton className="h-21 rounded-b-none" />
        <Skeleton className="h-28 rounded-b-none" />
        <Skeleton className="h-16 rounded-b-none" />
      </div>
      <ol className="divide-y rounded-lg border bg-card" aria-hidden>
        {[0, 1, 2, 3].map((row) => (
          <li key={row} className="flex items-center gap-3 px-4 py-3 sm:px-5">
            <SkeletonText className="w-8 shrink-0" />
            <Skeleton className="size-9 shrink-0 rounded-full" />
            <SkeletonText className="min-w-0 flex-1" />
            <SkeletonText className="w-16 shrink-0" />
          </li>
        ))}
      </ol>
    </SkeletonRegion>
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
