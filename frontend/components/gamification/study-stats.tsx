"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronRight, Flame, Medal, Trophy } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Mascot } from "@/components/mascot/mascot";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Skeleton, SkeletonInline, SkeletonText } from "@/components/ui/skeleton";
import { apiErrorMessage } from "@/lib/api/error-messages";
import {
  getMyGamification,
  listMyXpEvents,
  type GamificationSummary,
  type XpEvent,
  type XpReason,
} from "@/lib/api/gamification";
import { getLeaderboard, type Leaderboard } from "@/lib/api/leaderboard";
import { useAuth } from "@/lib/auth/auth-provider";
import { formatRelativeTime } from "@/lib/format";
import { formatXp, medalFor } from "@/lib/gamification/rank-view";
import { readItem, streakSeenKey, writeItem } from "@/lib/gamification/seen";
import {
  streakCopy,
  streakMood,
  streakReaction,
  streakSentence,
  streakState,
  vietnamDay,
  weekStrip,
  type DayCell,
  type StreakSeen,
  type StreakState,
} from "@/lib/gamification/streak-view";
import { cn } from "@/lib/utils";

const REASON_LABELS: Record<XpReason, string> = {
  lesson_completed: "Hoàn thành bài học",
  quiz_passed: "Vượt qua bài trắc nghiệm",
  exercise_solved: "Giải được bài tập code",
};

/** What each reason pays -- `XP_AMOUNTS` in `backend/app/services/gamification.py`. */
const XP_RULES = "bài học +10, bài trắc nghiệm đạt +20, bài code AC +30";

const MEDAL_CLASSES = { gold: "text-medal-gold", silver: "text-medal-silver", bronze: "text-medal-bronze" } as const;

/**
 * The achievements beside "Khóa học của tôi": the streak, with Naomi and this
 * week's seven days, then XP, this week's rank and the latest XP.
 *
 * Refetched every time the page mounts rather than trusting the app-wide
 * minute of staleness: a student who has just finished a lesson and comes
 * here to see it counted must not be shown the number from before.
 */
export function StudyStats() {
  const { accessToken, status, user } = useAuth();
  const enabled = status === "authenticated" && accessToken !== null;

  const summary = useQuery({
    queryKey: ["gamification", "summary"],
    queryFn: () => getMyGamification(accessToken as string),
    enabled,
    staleTime: 0,
  });
  const recent = useQuery({
    queryKey: ["gamification", "recent"],
    queryFn: () => listMyXpEvents(accessToken as string),
    enabled,
    staleTime: 0,
  });
  // The same request as the leaderboard's first page: one fetch between them.
  const week = useQuery({
    queryKey: ["leaderboard", "week", 1],
    queryFn: () => getLeaderboard(accessToken as string, "week", 1),
    enabled,
    staleTime: 30_000,
  });

  // The list beside this already says "đăng nhập"; saying it twice helps nobody.
  if (status === "anonymous") return null;

  if (summary.isError) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{apiErrorMessage(summary.error)}</AlertDescription>
      </Alert>
    );
  }

  const data = summary.data;

  return (
    <section aria-labelledby="study-stats-title" aria-busy={!data} className="flex min-w-0 flex-col gap-4">
      <h2 id="study-stats-title" className="sr-only">
        Thành tích học tập
      </h2>
      {data && user ? <StreakCardFor summary={data} userId={user.id} /> : <StreakSkeleton />}
      <XpCard summary={data} recent={recent.data?.items} week={week.data} />
    </section>
  );
}

/** A new state or a new day is a new card: it decides afresh whether Naomi reacts. */
function StreakCardFor({ summary, userId }: { summary: GamificationSummary; userId: string }) {
  const today = vietnamDay(new Date());
  const state = streakState(summary, today);
  return (
    <StreakCard
      key={`${state}:${summary.last_active_date}:${today}`}
      summary={summary}
      state={state}
      today={today}
      userId={userId}
    />
  );
}

function readSeen(userId: string): StreakSeen {
  try {
    const parsed: unknown = JSON.parse(readItem("local", streakSeenKey(userId)) ?? "{}");
    return parsed && typeof parsed === "object" ? (parsed as StreakSeen) : {};
  } catch {
    return {};
  }
}

function StreakCard({
  summary,
  state,
  today,
  userId,
}: {
  summary: GamificationSummary;
  state: StreakState;
  today: string;
  userId: string;
}) {
  // Decided once, when the card mounts with its data -- in the browser only,
  // since the numbers never reach the server render. Naomi reacts the first
  // time today's day is seen counted, or a broken streak is seen at all.
  const [reaction] = useState(() => streakReaction(summary, state, readSeen(userId)));
  useEffect(() => {
    if (reaction.event) writeItem("local", streakSeenKey(userId), JSON.stringify(reaction.seen));
  }, [reaction, userId]);

  const copy = streakCopy(summary, state);
  const mood = streakMood(state);
  const burning = state === "lit" || state === "pending";

  return (
    <div
      data-streak={state}
      className={cn(
        "flex flex-col gap-4 rounded-lg p-4 sm:p-5",
        burning ? "bg-reward-soft" : "border bg-card",
      )}
    >
      <div className="flex items-center gap-3 sm:gap-4">
        {mood ? (
          <Mascot mood={mood} event={reaction.event} className="size-20 sm:size-28" />
        ) : (
          <span className="flex size-14 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
            <Flame className="size-6" aria-hidden />
          </span>
        )}
        <div className="flex min-w-0 flex-col gap-0.5">
          <h3 className={cn("text-eyebrow uppercase", burning ? "text-streak-text" : "text-muted-foreground")}>
            Chuỗi ngày học
          </h3>
          <p
            className={cn(
              "tabular-nums",
              burning ? "text-numeral font-bold text-streak-text" : state === "lost" ? "text-h3" : "text-numeral",
            )}
          >
            {copy.value}
          </p>
          <p className={cn("text-body-sm", burning ? "text-reward-foreground" : "text-muted-foreground")}>
            {copy.note}
          </p>
        </div>
      </div>

      {burning ? (
        <>
          <WeekStrip cells={weekStrip(summary, today)} />
          <p className="sr-only">{streakSentence(summary, today)}</p>
          <p className="flex items-center gap-1.5 border-t border-reward/40 pt-3 text-body-sm text-reward-foreground">
            <Trophy className="size-4 shrink-0 text-reward-mark" aria-hidden />
            Chuỗi dài nhất: <strong className="font-semibold">{summary.longest_streak} ngày</strong>
          </p>
        </>
      ) : copy.detail ? (
        <p className="text-body-sm">{copy.detail}</p>
      ) : null}
    </div>
  );
}

/** This week, Monday to Sunday, drawn as dots: the sentence beside it is what a screen reader hears. */
function WeekStrip({ cells }: { cells: DayCell[] }) {
  return (
    <ol aria-hidden className="grid grid-cols-7 gap-0.5 text-center sm:gap-1">
      {cells.map((cell) => (
        <li key={cell.day} className="flex flex-col items-center gap-1">
          <span
            className={cn(
              "text-caption",
              cell.today ? "font-bold text-streak-text" : "text-muted-foreground",
            )}
          >
            {cell.label}
          </span>
          <span
            data-day={cell.state}
            className={cn(
              "flex size-7.5 items-center justify-center rounded-full sm:size-8",
              cell.state === "done" && "bg-streak text-card",
              cell.state === "done" && cell.today && "outline-2 outline-offset-2 outline-streak-text",
              cell.state === "open" && "border-2 border-dashed border-streak bg-card text-streak",
              cell.state === "off" && "border border-border-strong bg-card",
              cell.state === "later" && "border border-dashed border-border-strong",
            )}
          >
            {cell.state === "done" ? (
              <Flame className="size-4 fill-current" />
            ) : cell.state === "open" ? (
              <Flame className="size-4" />
            ) : null}
          </span>
        </li>
      ))}
    </ol>
  );
}

function StreakSkeleton() {
  return (
    <div aria-hidden className="flex flex-col gap-4 rounded-lg bg-reward-soft p-4 sm:p-5">
      <div className="flex items-center gap-3 sm:gap-4">
        <span className="size-20 shrink-0 sm:size-28" />
        <div className="flex flex-1 flex-col gap-1">
          <SkeletonText size="caption" className="w-28" />
          <Skeleton className="h-8 w-32" />
          <SkeletonText size="body-sm" className="w-40" />
        </div>
      </div>
      <Skeleton className="h-13 w-full" />
      <SkeletonText size="body-sm" className="w-36" />
    </div>
  );
}

function XpCard({
  summary,
  recent,
  week,
}: {
  summary: GamificationSummary | undefined;
  recent: XpEvent[] | undefined;
  week: Leaderboard | undefined;
}) {
  return (
    <div className="flex flex-col gap-3 rounded-lg border bg-card p-4 sm:p-5">
      <div className="flex flex-wrap items-end justify-between gap-x-3 gap-y-1">
        <div className="flex flex-col">
          <h3 className="text-eyebrow text-muted-foreground uppercase">Tổng XP</h3>
          <p className="text-numeral font-bold tabular-nums">
            {summary ? formatXp(summary.xp_total) : <SkeletonInline className="w-[6ch]" />}
          </p>
        </div>
        <RankLink week={week} />
      </div>

      <div className="border-t pt-3">
        <h3 className="text-body-sm font-semibold">XP gần đây</h3>
        {recent && recent.length > 0 ? (
          <ul className="mt-1 divide-y divide-muted">
            {recent.map((event) => (
              <XpRow key={event.id} event={event} />
            ))}
          </ul>
        ) : recent ? (
          // One line, not Naomi: the course list beside this is the page's
          // empty state, and one Naomi per screen is enough.
          <p className="mt-1 text-body-sm text-muted-foreground">
            Chưa có XP nào. Hoàn thành bài học đầu tiên để nhận 10 XP.
          </p>
        ) : (
          <ul className="mt-1 divide-y divide-muted" aria-hidden>
            {[0, 1, 2, 3, 4].map((row) => (
              <li key={row} className="flex items-center gap-2.5 py-2">
                <Skeleton className="h-5.5 w-14 shrink-0 rounded-full" />
                <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                  <SkeletonText size="body-sm" className={row % 2 ? "w-1/2" : "w-3/4"} />
                  <SkeletonText size="caption" className="w-2/5" />
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <p className="border-t pt-3 text-caption text-muted-foreground">
        XP tính ở lần hoàn thành đầu tiên: {XP_RULES}. Một ngày vào chuỗi khi bạn hoàn thành bài
        học, nộp bài trắc nghiệm hoặc nộp bài code (giờ Việt Nam).
      </p>
    </div>
  );
}

/** "Hạng 1 tuần này", with a medal on the podium; a plain way in without XP this week. */
function RankLink({ week }: { week: Leaderboard | undefined }) {
  const rank = week?.me?.rank ?? null;
  const medal = rank === null ? null : medalFor(rank);
  const Icon = medal ? Medal : Trophy;
  return (
    <Link
      href="/bang-xep-hang"
      className={cn(
        "flex min-h-6 items-center gap-1.5 pb-1 text-body-sm font-semibold hover:underline hover:underline-offset-4",
        rank === null ? "text-link" : "text-foreground",
      )}
    >
      <Icon
        className={cn("size-4 shrink-0", medal ? MEDAL_CLASSES[medal] : rank === null ? "" : "text-muted-foreground")}
        aria-hidden
      />
      {rank === null ? "Xem bảng xếp hạng" : `Hạng ${rank} tuần này`}
      {rank !== null ? <ChevronRight className="size-4 shrink-0 text-muted-foreground" aria-hidden /> : null}
    </Link>
  );
}

function XpRow({ event }: { event: XpEvent }) {
  return (
    <li className="flex items-center gap-2.5 py-2">
      <Badge variant="reward" className="w-14 shrink-0">
        +{event.amount} XP
      </Badge>
      <span className="flex min-w-0 flex-1 flex-col">
        {event.lesson && event.course ? (
          <Link
            href={`/hoc/${event.course.slug}?bai=${event.lesson.id}`}
            className="line-clamp-1 text-body-sm font-medium hover:underline hover:underline-offset-4"
          >
            {event.lesson.title}
          </Link>
        ) : (
          <span className="line-clamp-1 text-body-sm text-muted-foreground">Bài học đã bị xóa</span>
        )}
        <span className="text-caption text-muted-foreground">
          {REASON_LABELS[event.reason]} ·{" "}
          <time dateTime={event.created_at}>{formatRelativeTime(event.created_at)}</time>
        </span>
      </span>
    </li>
  );
}
