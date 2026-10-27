"use client";

import { useQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { QA_KEY } from "@/components/qa/qa-shared";
import { Button } from "@/components/ui/button";
import { listInstructorThreads } from "@/lib/api/qa";
import { useAuth } from "@/lib/auth/auth-provider";
import { cn } from "@/lib/utils";

const PLACES = [
  { href: "/giang-day", label: "Khóa học" },
  { href: "/giang-day/hoi-dap", label: "Hỏi đáp" },
  { href: "/giang-day/thong-ke", label: "Thống kê" },
  { href: "/giang-day/cap-bac", label: "Cấp bậc" },
] as const;

/** Which place a path belongs to: a course being edited, or a new one, is "Khóa học". */
function placeOf(pathname: string): string {
  const other = PLACES.slice(1).find((place) => pathname.startsWith(place.href));
  return other ? other.href : "/giang-day";
}

/** The query behind the badge on "Hỏi đáp", shared with the overview's task list. */
export function useUnansweredCount() {
  const { accessToken } = useAuth();
  return useQuery({
    // Under QA_KEY so a reply anywhere refreshes the count.
    queryKey: [...QA_KEY, "inbox", "unanswered-count"],
    queryFn: () =>
      listInstructorThreads(accessToken as string, { courseId: null, unanswered: true, page: 1 }),
    enabled: accessToken !== null,
    select: (page) => page.total,
  });
}

/**
 * One bar of places under the site header, the same on every instructor
 * screen: it replaces the back links and the row of buttons the course list
 * used to carry. On a phone it scrolls sideways and the create button moves
 * into the overview.
 */
export function InstructorNav() {
  const pathname = usePathname();
  const current = placeOf(pathname);
  const unanswered = useUnansweredCount();
  const count = unanswered.data ?? 0;

  return (
    <div className="border-b bg-card">
      <div className="mx-auto flex max-w-6xl items-center gap-6 px-4">
        <span className="hidden text-eyebrow text-muted-foreground md:inline">Giảng dạy</span>
        <nav aria-label="Khu giảng viên" className="relative -mx-2 flex min-w-0 flex-1 overflow-x-auto md:mx-0">
          {PLACES.map((place) => {
            const active = place.href === current;
            return (
              <Link
                key={place.href}
                href={place.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "relative inline-flex h-12 shrink-0 items-center gap-2 px-3 text-body-sm whitespace-nowrap transition-colors duration-fast after:absolute after:inset-x-2 after:bottom-0 after:h-0.5 after:rounded-full md:h-13 md:text-body",
                  active
                    ? "font-semibold text-foreground after:bg-primary"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                {place.label}
                {place.href === "/giang-day/hoi-dap" && count > 0 ? (
                  <span className="inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-primary px-1.5 text-xs font-semibold text-primary-foreground tabular-nums">
                    {count}
                    <span className="sr-only"> câu chờ trả lời</span>
                  </span>
                ) : null}
              </Link>
            );
          })}
        </nav>
        {pathname === "/giang-day/moi" ? null : (
          <Button
            asChild
            variant={pathname === "/giang-day" ? "default" : "outline"}
            className="hidden sm:inline-flex"
          >
            <Link href="/giang-day/moi">
              <Plus aria-hidden />
              Tạo khóa học
            </Link>
          </Button>
        )}
      </div>
    </div>
  );
}
