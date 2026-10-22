"use client";

import { useQuery } from "@tanstack/react-query";
import { Flame, Sparkles, Trophy } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { SkeletonInline } from "@/components/ui/skeleton";
import { apiErrorMessage } from "@/lib/api/error-messages";
import {
  getMyGamification,
  listMyXpEvents,
  type GamificationSummary,
  type XpReason,
} from "@/lib/api/gamification";
import { useAuth } from "@/lib/auth/auth-provider";
import { formatRelativeTime } from "@/lib/format";
import { cn } from "@/lib/utils";

const REASON_LABELS: Record<XpReason, string> = {
  lesson_completed: "Hoàn thành bài học",
  quiz_passed: "Vượt qua bài trắc nghiệm",
  exercise_solved: "Giải được bài tập code",
};

/** What each reason pays -- `XP_AMOUNTS` in `backend/app/services/gamification.py`. */
const XP_RULES = "bài học +10 XP, bài trắc nghiệm đạt +20 XP, bài tập code AC +30 XP";

/**
 * Streak and XP, above "Khóa học của tôi".
 *
 * Refetched every time the page mounts rather than trusting the app-wide
 * minute of staleness: a student who has just finished a lesson and comes
 * here to see it counted must not be shown the number from before.
 */
export function StudyStats() {
  const { accessToken, status } = useAuth();
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

  // The list below already says "đăng nhập"; saying it twice helps nobody.
  if (status === "anonymous") return null;

  if (summary.isError) {
    return (
      <Alert variant="destructive" className="mb-8">
        <AlertDescription>{apiErrorMessage(summary.error)}</AlertDescription>
      </Alert>
    );
  }

  // Until the numbers arrive -- and while the session itself is still being
  // restored -- the section is drawn whole, with grey bars where the numbers
  // go: labels, card and rules text take their real room, so the course list
  // below does not move when the data lands.
  const data = summary.data;

  return (
    <section aria-labelledby="study-stats-title" aria-busy={!data} className="mb-10 space-y-4">
      <h2 id="study-stats-title" className="sr-only">
        Thành tích học tập
      </h2>

      {/* Three across even on a phone: stacked, the tiles pushed the
          course list (or its empty state) a whole screen down. */}
      <div className="grid grid-cols-3 gap-2 sm:gap-4">
        <Tile
          icon={
            <Flame
              className={cn(
                "size-5",
                data?.active_today ? "text-orange-500" : "text-muted-foreground",
              )}
              aria-hidden
            />
          }
          label="Chuỗi ngày học"
          value={data ? `${data.current_streak} ngày` : null}
          note={data ? streakNote(data) : null}
        />
        <Tile
          icon={<Trophy className="size-5 text-amber-500" aria-hidden />}
          label="Chuỗi dài nhất"
          value={data ? `${data.longest_streak} ngày` : null}
        />
        <Tile
          icon={<Sparkles className="size-5 text-primary" aria-hidden />}
          label="Tổng XP"
          value={data ? `${data.xp_total.toLocaleString("vi-VN")} XP` : null}
        />
      </div>

      <div className="rounded-lg border bg-card p-4">
        <div className="flex items-baseline justify-between gap-3">
          <h3 className="text-sm font-medium">XP gần đây</h3>
          <Link href="/bang-xep-hang" className="text-sm font-medium text-primary hover:underline">
            Xem bảng xếp hạng
          </Link>
        </div>
        {recent.data && recent.data.items.length > 0 ? (
          <ul className="mt-3 divide-y">
            {recent.data.items.map((event) => (
              <li key={event.id} className="flex items-center gap-3 py-2 text-sm">
                <span className="w-16 shrink-0 font-semibold tabular-nums text-primary">
                  +{event.amount} XP
                </span>
                <span className="min-w-0 flex-1">
                  <span className="text-muted-foreground">{REASON_LABELS[event.reason]}</span>
                  {event.lesson && event.course ? (
                    <>
                      {" · "}
                      <Link
                        href={`/hoc/${event.course.slug}?bai=${event.lesson.id}`}
                        className="font-medium hover:underline"
                      >
                        {event.lesson.title}
                      </Link>
                    </>
                  ) : (
                    <span className="text-muted-foreground"> · bài học đã bị xóa</span>
                  )}
                </span>
                <time
                  dateTime={event.created_at}
                  className="shrink-0 text-xs text-muted-foreground"
                >
                  {formatRelativeTime(event.created_at)}
                </time>
              </li>
            ))}
          </ul>
        ) : recent.data ? (
          // One line, not Naomi: the course list below is this page's empty
          // state, and one Naomi per screen is enough.
          <p className="mt-2 text-sm text-muted-foreground">
            Chưa có XP nào. Hoàn thành bài học đầu tiên để nhận 10 XP.
          </p>
        ) : (
          // The five rows the list asks for, row for row: one line from `sm`,
          // two on a phone, where the lesson titles wrap.
          <ul className="mt-3 divide-y" aria-hidden>
            {[0, 1, 2, 3, 4].map((row) => (
              <li key={row} className="flex h-14 items-center gap-3 py-2 text-sm sm:h-9">
                <span className="w-16 shrink-0">
                  <SkeletonInline className="w-12" />
                </span>
                <span className="min-w-0 flex-1">
                  <SkeletonInline className={row % 2 ? "w-1/2" : "w-3/4"} />
                </span>
                <span className="shrink-0 text-xs">
                  <SkeletonInline className="w-14" />
                </span>
              </li>
            ))}
          </ul>
        )}
        <p className="mt-3 border-t pt-3 text-xs text-muted-foreground">
          XP chỉ tính ở lần hoàn thành đầu tiên: {XP_RULES}. Một ngày được tính vào
          chuỗi khi bạn hoàn thành bài học, nộp bài trắc nghiệm hoặc nộp bài code
          (theo giờ Việt Nam).
        </p>
      </div>
    </section>
  );
}

function streakNote(data: GamificationSummary): string {
  if (data.active_today) return "Hôm nay đã được tính";
  if (data.current_streak > 0) return "Học một bài hôm nay để giữ chuỗi";
  return "Hoàn thành một bài để bắt đầu chuỗi mới";
}

function Tile({
  icon,
  label,
  value,
  note,
}: {
  icon: ReactNode;
  label: string;
  /** `null` while loading: a bar in the same line. */
  value: string | null;
  /** `null` while loading a note that will come; leave out for none. */
  note?: string | null;
}) {
  return (
    // A column with the number pushed to the bottom on a phone, where one label
    // wraps and the others do not and the three numbers should still line up.
    // From `sm` up the labels fit and a note may follow, so it stays at the top.
    <div className="flex min-w-0 flex-col rounded-lg border bg-card p-3 sm:p-4">
      <p className="flex flex-col items-start gap-1 text-xs text-muted-foreground sm:flex-row sm:items-center sm:gap-2 sm:text-sm">
        {icon}
        {label}
      </p>
      <p className="mt-auto pt-1 text-lg font-semibold tracking-tight sm:mt-0 sm:text-2xl">
        {value ?? <SkeletonInline className="w-[4ch]" />}
      </p>
      {note !== undefined ? (
        <p className="mt-1 hidden text-xs text-muted-foreground sm:block">
          {note ?? <SkeletonInline className="w-[16ch]" />}
        </p>
      ) : null}
    </div>
  );
}
