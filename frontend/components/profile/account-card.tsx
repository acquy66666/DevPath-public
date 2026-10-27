"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { AVATAR_RULE, AvatarForm } from "@/components/profile/avatar-form";
import type { User } from "@/lib/api/auth";
import { getMyGamification } from "@/lib/api/gamification";
import { useAuth } from "@/lib/auth/auth-provider";
import { ROLE_LABELS } from "@/lib/auth/roles";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";

/**
 * Who this account is, at the top of the profile: the picture (changed right
 * here), name, email, role, since when -- and two numbers from learning, each
 * a way into the page that explains it. Staff accounts learn too, so they get
 * the numbers as well.
 */
export function AccountCard({ user }: { user: User }) {
  const { accessToken } = useAuth();
  const summary = useQuery({
    // Keyed by account: the cache outlives a sign-out, and another person's
    // streak must not flash up here while this one's loads.
    queryKey: ["gamification", "summary", user.id],
    queryFn: () => getMyGamification(accessToken as string),
    enabled: accessToken !== null,
    staleTime: 0,
  });

  const streak = summary.data?.current_streak ?? 0;

  return (
    <section
      aria-label="Tài khoản"
      className="flex flex-col gap-5 rounded-xl border bg-card p-5 md:flex-row md:flex-wrap md:items-center md:gap-x-8 md:gap-y-6 md:p-7"
    >
      <div className="flex min-w-0 items-center gap-4 md:flex-[999_1_26rem] md:gap-5">
        <AvatarForm user={user} />
        <div className="min-w-0 space-y-1.5">
          <p className="text-h2 break-words">{user.full_name}</p>
          <p className="text-body-sm break-all text-muted-foreground md:text-body">{user.email}</p>
          <p className="flex flex-wrap gap-2 pt-0.5 text-caption">
            <span className="rounded-full bg-secondary px-2.5 py-0.5 font-semibold text-secondary-foreground">
              {ROLE_LABELS[user.role]}
            </span>
            <span className="rounded-full bg-muted px-2.5 py-0.5 text-foreground/80">
              Tham gia {formatDate(user.created_at)}
            </span>
          </p>
          <p id={AVATAR_RULE.id} className="text-caption text-muted-foreground">
            {AVATAR_RULE.text}
          </p>
        </div>
      </div>

      <ul aria-label="Học tập" className="grid grid-cols-2 gap-2.5 md:flex-[1_1_16rem] md:gap-3">
        <Stat
          href="/khoa-hoc-cua-toi"
          label="Chuỗi ngày"
          value={summary.data ? `${streak} ngày` : null}
          warm={streak > 0}
        />
        <Stat
          href="/bang-xep-hang"
          label="Tổng XP"
          value={summary.data ? `${summary.data.xp_total.toLocaleString("vi-VN")} XP` : null}
        />
      </ul>
    </section>
  );
}

function Stat({
  href,
  label,
  value,
  warm = false,
}: {
  href: string;
  label: string;
  value: string | null;
  warm?: boolean;
}) {
  return (
    <li>
    <Link
      href={href}
      className={cn(
        "flex h-full flex-col gap-0.5 rounded-lg px-3.5 py-3 transition-colors md:px-4 md:py-3.5",
        warm ? "bg-reward-soft text-reward-foreground hover:bg-reward-soft/70" : "bg-muted hover:bg-accent",
      )}
    >
      <span className={cn("text-eyebrow uppercase", !warm && "text-muted-foreground")}>{label}</span>
      <span className="text-h2 tabular-nums">
        {/* Same height as the number, so nothing moves when it lands. */}
        {value ?? <span className="text-muted-foreground">…<span className="sr-only"> đang tải</span></span>}
      </span>
    </Link>
    </li>
  );
}
