"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Award,
  BookCheck,
  Flag,
  FolderTree,
  ImageIcon,
  LayoutDashboard,
  LineChart,
  PiggyBank,
  Receipt,
  TicketPercent,
  Trophy,
  Users,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { getAdminSummary } from "@/lib/api/admin";
import { useAuth } from "@/lib/auth/auth-provider";
import { cn } from "@/lib/utils";

/** Every admin query sits under this key, so one decision refreshes the badges too. */
export const ADMIN_KEY = ["admin"] as const;

interface Tab {
  href: string;
  label: string;
  icon: LucideIcon;
  count: (summary: { pending_courses: number; pending_reports: number }) => number;
}

const TABS: Tab[] = [
  { href: "/quan-tri", label: "Tổng quan", icon: LayoutDashboard, count: () => 0 },
  // Money lives here and nowhere an instructor can reach (20/10/2026).
  { href: "/quan-tri/doanh-thu", label: "Doanh thu", icon: LineChart, count: () => 0 },
  { href: "/quan-tri/xep-hang", label: "Xếp hạng", icon: Trophy, count: () => 0 },
  { href: "/quan-tri/cap-giang-vien", label: "Cấp giảng viên", icon: Award, count: () => 0 },
  { href: "/quan-tri/thanh-toan", label: "Thanh toán GV", icon: Receipt, count: () => 0 },
  { href: "/quan-tri/loi-nhuan", label: "Lợi nhuận", icon: PiggyBank, count: () => 0 },
  { href: "/quan-tri/khoa-hoc", label: "Duyệt khóa học", icon: BookCheck, count: (s) => s.pending_courses },
  { href: "/quan-tri/bao-cao", label: "Báo cáo vi phạm", icon: Flag, count: (s) => s.pending_reports },
  { href: "/quan-tri/nguoi-dung", label: "Người dùng", icon: Users, count: () => 0 },
  { href: "/quan-tri/danh-muc", label: "Danh mục", icon: FolderTree, count: () => 0 },
  { href: "/quan-tri/ma-giam-gia", label: "Mã giảm giá", icon: TicketPercent, count: () => 0 },
  { href: "/quan-tri/banner", label: "Banner", icon: ImageIcon, count: () => 0 },
];

/**
 * The admin area's tabs, each with what is waiting behind it.
 *
 * Links rather than `Tabs`: each is its own URL, so the back button and a
 * bookmark land where they should.
 */
export function AdminNav() {
  const { accessToken } = useAuth();
  const pathname = usePathname();

  const summary = useQuery({
    queryKey: [...ADMIN_KEY, "summary"],
    queryFn: () => getAdminSummary(accessToken as string),
    enabled: accessToken !== null,
    refetchInterval: 60_000,
  });

  return (
    <div className="space-y-4 print:hidden">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Quản trị</h1>
        <p className="text-sm text-muted-foreground">
          Doanh thu, cấp và thanh toán giảng viên, lợi nhuận; duyệt khóa học, xử lý báo cáo vi
          phạm và quản lý tài khoản.
        </p>
      </div>
      <nav aria-label="Khu vực quản trị" className="-mx-4 overflow-x-auto px-4">
        <ul className="flex min-w-max gap-1 border-b">
          {TABS.map((tab) => {
            // "/quan-tri" is the parent of every other tab: it is only active on itself.
            const active =
              pathname === tab.href ||
              (tab.href !== "/quan-tri" && pathname.startsWith(`${tab.href}/`));
            const count = summary.data ? tab.count(summary.data) : 0;
            return (
              <li key={tab.href}>
                <Link
                  href={tab.href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "-mb-px flex items-center gap-2 border-b-2 px-3 py-2 text-sm transition-colors focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none",
                    active
                      ? "border-primary font-medium text-foreground"
                      : "border-transparent text-muted-foreground hover:text-foreground",
                  )}
                >
                  <tab.icon className="size-4" aria-hidden />
                  {tab.label}
                  {count > 0 ? (
                    <span
                      className="rounded-full bg-primary px-1.5 text-xs leading-5 font-medium text-primary-foreground tabular-nums"
                      aria-label={`${count} đang chờ`}
                    >
                      {count}
                    </span>
                  ) : null}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </div>
  );
}
