"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Award,
  BookCheck,
  ChevronDown,
  Flag,
  FolderTree,
  ImageIcon,
  LayoutDashboard,
  LineChart,
  PiggyBank,
  Receipt,
  TicketPercent,
  Trophy,
  UserCheck,
  Users,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";

import { getAdminSummary, type AdminSummary } from "@/lib/api/admin";
import { badgeCount, PLACE_GROUPS, placeOf, waitingTotal, type Place } from "@/lib/admin/admin-view";
import { useAuth } from "@/lib/auth/auth-provider";
import { cn } from "@/lib/utils";

/** Every admin query sits under this key, so one decision refreshes the badges too. */
export const ADMIN_KEY = ["admin"] as const;

const ICONS: Record<string, LucideIcon> = {
  "/quan-tri": LayoutDashboard,
  "/quan-tri/khoa-hoc": BookCheck,
  "/quan-tri/duyet-giang-vien": UserCheck,
  "/quan-tri/bao-cao": Flag,
  "/quan-tri/nguoi-dung": Users,
  "/quan-tri/doanh-thu": LineChart,
  "/quan-tri/xep-hang": Trophy,
  "/quan-tri/cap-giang-vien": Award,
  "/quan-tri/thanh-toan": Receipt,
  "/quan-tri/loi-nhuan": PiggyBank,
  "/quan-tri/danh-muc": FolderTree,
  "/quan-tri/ma-giam-gia": TicketPercent,
  "/quan-tri/banner": ImageIcon,
};

/** The counts behind the badges, shared by the menu and the overview. */
export function useAdminSummary() {
  const { accessToken } = useAuth();
  return useQuery({
    queryKey: [...ADMIN_KEY, "summary"],
    queryFn: () => getAdminSummary(accessToken as string),
    enabled: accessToken !== null,
    refetchInterval: 60_000,
  });
}

/**
 * The admin area's places, grouped: a side menu from `lg`, one button that
 * names the current place and folds the same list out below that.
 *
 * Links rather than tabs: each place is its own URL, so the back button and a
 * bookmark land where they should.
 */
export function AdminNav() {
  const pathname = usePathname();
  const current = placeOf(pathname);
  const summary = useAdminSummary().data;

  return (
    <>
      <aside className="-ml-3 hidden w-60 shrink-0 lg:block print:hidden">
        <nav aria-label="Khu vực quản trị" className="sticky top-6">
          <PlaceList current={current} summary={summary} />
        </nav>
      </aside>
      <FoldedNav current={current} summary={summary} />
    </>
  );
}

function PlaceList({
  current,
  summary,
  onPick,
}: {
  current: Place;
  summary: AdminSummary | undefined;
  onPick?: () => void;
}) {
  return (
    <div className="space-y-5">
      {PLACE_GROUPS.map((group) => (
        <div key={group.label ?? "overview"} className="space-y-0.5">
          {/* The overview's group has no name of its own: the area's name stands over it. */}
          <p className="px-3 pb-1.5 text-eyebrow text-muted-foreground">
            {group.label ?? "Quản trị"}
          </p>
          <ul className="space-y-0.5">
            {group.places.map((place) => (
              <li key={place.href}>
                <PlaceLink
                  place={place}
                  active={place.href === current.href}
                  count={badgeCount(place, summary)}
                  onPick={onPick}
                />
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

function PlaceLink({
  place,
  active,
  count,
  onPick,
}: {
  place: Place;
  active: boolean;
  count: number;
  onPick?: () => void;
}) {
  const Icon = ICONS[place.href];
  return (
    <Link
      href={place.href}
      aria-current={active ? "page" : undefined}
      onClick={onPick}
      className={cn(
        "flex h-11 items-center gap-2.5 rounded-md px-3 text-body transition-colors duration-fast lg:h-10",
        active
          ? "bg-secondary font-semibold text-secondary-foreground"
          : "text-muted-foreground hover:bg-accent hover:text-foreground",
      )}
    >
      {Icon ? <Icon className="size-4.5 shrink-0" aria-hidden /> : null}
      <span className="min-w-0 flex-1 truncate">{place.label}</span>
      {count > 0 ? <CountBadge count={count} /> : null}
    </Link>
  );
}

function CountBadge({ count, label = "đang chờ" }: { count: number; label?: string }) {
  return (
    <span className="inline-flex h-5.5 min-w-5.5 shrink-0 items-center justify-center rounded-full bg-primary px-1.5 text-xs font-semibold text-primary-foreground tabular-nums">
      {count}
      <span className="sr-only"> {label}</span>
    </span>
  );
}

/** Below `lg`: the side menu folded into a button that says where you are. */
function FoldedNav({ current, summary }: { current: Place; summary: AdminSummary | undefined }) {
  const [open, setOpen] = useState(false);
  const listId = useId();
  const button = useRef<HTMLButtonElement>(null);
  const waiting = waitingTotal(summary);

  // Escape folds it back and returns focus to the button.
  useEffect(() => {
    if (!open) return;
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
        button.current?.focus();
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <div className="lg:hidden print:hidden">
      <button
        ref={button}
        type="button"
        aria-expanded={open}
        aria-controls={listId}
        onClick={() => setOpen((value) => !value)}
        className="flex h-11 w-full items-center gap-2.5 rounded-md border border-border-strong bg-card px-3.5 text-left text-body"
      >
        <span className="text-eyebrow text-muted-foreground">Quản trị</span>
        <span className="min-w-0 flex-1 truncate font-semibold">{current.label}</span>
        {waiting > 0 ? <CountBadge count={waiting} label="việc đang chờ" /> : null}
        <ChevronDown
          className={cn("size-4.5 shrink-0 transition-transform duration-fast motion-reduce:transition-none", open && "rotate-180")}
          aria-hidden
        />
      </button>
      <nav
        id={listId}
        aria-label="Khu vực quản trị"
        hidden={!open}
        className="mt-2 rounded-lg border bg-card p-2 shadow-md"
      >
        <PlaceList current={current} summary={summary} onPick={() => setOpen(false)} />
      </nav>
    </div>
  );
}
