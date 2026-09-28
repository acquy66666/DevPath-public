"use client";

import { useQuery } from "@tanstack/react-query";
import { Flame, Sparkles, Trophy } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
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
  if (status !== "authenticated") return null;

  if (summary.isError) {
    return (
      <Alert variant="destructive" className="mb-8">
        <AlertDescription>{apiErrorMessage(summary.error)}</AlertDescription>
      </Alert>
    );
  }

  if (!summary.data) {
    return (
      <div className="mb-8 grid gap-4 sm:grid-cols-3" aria-hidden>
        {[0, 1, 2].map((tile) => (
          <div key={tile} className="h-28 animate-pulse rounded-xl border bg-muted/40" />
        ))}
      </div>
    );
  }

  const data = summary.data;

  return (
    <section aria-labelledby="study-stats-title" className="mb-10 space-y-4">
      <h2 id="study-stats-title" className="sr-only">
        Thành tích học tập
      </h2>

      <div className="grid gap-4 sm:grid-cols-3">
        <Tile
          icon={
            <Flame
              className={cn(
                "size-5",
                data.active_today ? "text-orange-500" : "text-muted-foreground",
              )}
              aria-hidden
            />
          }
          label="Chuỗi ngày học"
          value={`${data.current_streak} ngày`}
          note={streakNote(data)}
        />
        <Tile
          icon={<Trophy className="size-5 text-amber-500" aria-hidden />}
          label="Chuỗi dài nhất"
          value={`${data.longest_streak} ngày`}
        />
        <Tile
          icon={<Sparkles className="size-5 text-primary" aria-hidden />}
          label="Tổng XP"
          value={`${data.xp_total.toLocaleString("vi-VN")} XP`}
        />
      </div>

      <div className="rounded-xl border bg-card p-4">
        <h3 className="text-sm font-medium">XP gần đây</h3>
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
          <p className="mt-2 text-sm text-muted-foreground">
            Chưa có XP nào. Hoàn thành bài học đầu tiên để nhận 10 XP.
          </p>
        ) : (
          <div className="mt-3 h-24 animate-pulse rounded-md bg-muted/40" aria-hidden />
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
  value: string;
  note?: string;
}) {
  return (
    <div className="rounded-xl border bg-card p-4">
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        {icon}
        {label}
      </p>
      <p className="mt-1 text-2xl font-semibold tracking-tight">{value}</p>
      {note ? <p className="mt-1 text-xs text-muted-foreground">{note}</p> : null}
    </div>
  );
}
