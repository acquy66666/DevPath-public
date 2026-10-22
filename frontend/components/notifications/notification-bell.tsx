"use client";

import { useQuery } from "@tanstack/react-query";
import { Bell, CheckCheck, Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { getUnreadCount, listNotifications, type AppNotification } from "@/lib/api/notifications";
import { useAuth } from "@/lib/auth/auth-provider";

import { describe, NOTIFICATIONS_KEY, NotificationBody, useMarkRead } from "./notification-items";

/** How many the dropdown shows; the rest are one click away on the page. */
const RECENT = 8;

/**
 * How often the number is asked for while the tab is open. Nothing on the
 * page is urgent enough for a socket: an answer to a question can wait a
 * minute, and TanStack also asks again whenever the window regains focus.
 */
const POLL_MS = 60_000;

/**
 * The bell in the header: how many are unread, and the latest few.
 *
 * The count is its own cheap request, polled; the list is fetched only when
 * the menu opens, so a page that is merely open costs one small query a
 * minute and nothing more.
 */
export function NotificationBell() {
  const { accessToken, status } = useAuth();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const { one, all } = useMarkRead();
  const signedIn = status === "authenticated" && accessToken !== null;

  const count = useQuery({
    queryKey: [...NOTIFICATIONS_KEY, "unread-count"],
    queryFn: () => getUnreadCount(accessToken as string),
    enabled: signedIn,
    refetchInterval: POLL_MS,
  });

  const recent = useQuery({
    queryKey: [...NOTIFICATIONS_KEY, "list", false, 1, RECENT],
    queryFn: () =>
      listNotifications(accessToken as string, { unread: false, page: 1, pageSize: RECENT }),
    enabled: signedIn && open,
  });

  if (status !== "authenticated") return null;

  const unread = count.data?.count ?? 0;

  function follow(notification: AppNotification) {
    if (notification.read_at === null) one.mutate(notification.id);
    router.push(describe(notification).href);
  }

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="relative h-10 px-2 sm:px-3"
          aria-label={unread > 0 ? `Thông báo, ${unread} chưa đọc` : "Thông báo"}
        >
          <Bell className="size-5" aria-hidden />
          {unread > 0 ? (
            <span
              className="absolute -top-0.5 right-0 flex h-5 min-w-5 items-center justify-center rounded-full bg-destructive px-1 text-[0.7rem] font-semibold text-destructive-foreground tabular-nums"
              aria-hidden
            >
              {unread > 9 ? "9+" : unread}
            </span>
          ) : null}
        </Button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" className="w-[22rem] max-w-[calc(100vw-2rem)] p-0">
        <div className="flex items-center justify-between gap-2 px-3 py-2">
          <p className="text-sm font-semibold">Thông báo</p>
          {unread > 0 ? (
            <button
              type="button"
              className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground disabled:opacity-50"
              onClick={() => all.mutate()}
              disabled={all.isPending}
            >
              <CheckCheck className="size-3.5" aria-hidden />
              Đánh dấu đã đọc hết
            </button>
          ) : null}
        </div>
        <DropdownMenuSeparator className="my-0" />

        <div className="max-h-[26rem] overflow-y-auto p-1">
          {recent.isPending ? (
            <div className="flex justify-center py-6 text-muted-foreground">
              <Loader2 className="size-5 animate-spin" aria-label="Đang tải" />
            </div>
          ) : recent.isError ? (
            <p className="px-3 py-6 text-center text-sm text-destructive">
              {apiErrorMessage(recent.error)}
            </p>
          ) : recent.data.items.length === 0 ? (
            <div className="flex flex-col items-center gap-2 px-3 py-8 text-center">
              <Bell className="size-6 text-muted-foreground" aria-hidden />
              <p className="text-sm text-muted-foreground">Chưa có thông báo nào.</p>
            </div>
          ) : (
            recent.data.items.map((notification) => (
              <DropdownMenuItem
                key={notification.id}
                // The item is the whole row: selecting it (click or Enter)
                // marks it read and goes where it points.
                onSelect={() => follow(notification)}
                className={
                  notification.read_at === null
                    ? "items-start gap-3 bg-primary/5 p-2"
                    : "items-start gap-3 p-2"
                }
              >
                <NotificationBody notification={notification} />
              </DropdownMenuItem>
            ))
          )}
        </div>

        <DropdownMenuSeparator className="my-0" />
        <DropdownMenuItem asChild className="justify-center rounded-t-none py-2 text-sm">
          <Link href="/thong-bao">Xem tất cả thông báo</Link>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
