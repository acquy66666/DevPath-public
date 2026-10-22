"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Bell, CheckCheck, Loader2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Pager } from "@/components/ui/pager";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { getUnreadCount, listNotifications } from "@/lib/api/notifications";
import { useAuth } from "@/lib/auth/auth-provider";
import { cn } from "@/lib/utils";

import { NOTIFICATIONS_KEY, NotificationLink, useMarkRead } from "./notification-items";

/** Every notification, newest first, with "chưa đọc" one tab away. */
export function NotificationList() {
  const { accessToken, status } = useAuth();
  const [unread, setUnread] = useState(false);
  const [page, setPage] = useState(1);
  const { one, all } = useMarkRead();
  const signedIn = status === "authenticated" && accessToken !== null;

  const list = useQuery({
    queryKey: [...NOTIFICATIONS_KEY, "list", unread, page, 20],
    queryFn: () => listNotifications(accessToken as string, { unread, page }),
    enabled: signedIn,
    placeholderData: keepPreviousData,
  });

  // The same cache entry as the bell's, so the button below and the number in
  // the header can never disagree.
  const count = useQuery({
    queryKey: [...NOTIFICATIONS_KEY, "unread-count"],
    queryFn: () => getUnreadCount(accessToken as string),
    enabled: signedIn,
  });
  const unreadCount = count.data?.count ?? 0;

  if (status === "loading") {
    return <div className="h-64 animate-pulse rounded-lg bg-muted/50" aria-hidden />;
  }

  if (status === "anonymous") {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Đăng nhập để xem thông báo</CardTitle>
          <CardDescription>
            Thông báo cho bạn biết khi có người trả lời câu hỏi của bạn.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button asChild>
            <Link href="/dang-nhap?next=/thong-bao">Đăng nhập</Link>
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Tabs
          value={unread ? "unread" : "all"}
          onValueChange={(value) => {
            setUnread(value === "unread");
            setPage(1);
          }}
        >
          <TabsList>
            <TabsTrigger value="all">Tất cả</TabsTrigger>
            <TabsTrigger value="unread">
              Chưa đọc{unreadCount > 0 ? ` (${unreadCount})` : ""}
            </TabsTrigger>
          </TabsList>
        </Tabs>
        <Button
          variant="outline"
          size="sm"
          onClick={() => all.mutate()}
          disabled={all.isPending || unreadCount === 0}
        >
          {all.isPending ? (
            <Loader2 className="animate-spin" aria-hidden />
          ) : (
            <CheckCheck aria-hidden />
          )}
          Đánh dấu đã đọc hết
        </Button>
      </div>

      {list.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(list.error)}</AlertDescription>
        </Alert>
      ) : null}

      {list.isPending ? (
        <div className="space-y-2" aria-hidden>
          {[0, 1, 2, 3].map((row) => (
            <div key={row} className="h-16 animate-pulse rounded-md bg-muted/40" />
          ))}
        </div>
      ) : null}

      {list.data && list.data.total === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed px-4 py-12 text-center">
          <Bell className="size-8 text-muted-foreground" aria-hidden />
          <p className="font-medium">
            {unread ? "Bạn đã đọc hết thông báo" : "Chưa có thông báo nào"}
          </p>
          <p className="text-sm text-muted-foreground">
            Khi có người trả lời câu hỏi của bạn, hoặc học viên hỏi trong khóa bạn dạy, thông
            báo sẽ hiện ở đây.
          </p>
        </div>
      ) : null}

      {list.data && list.data.items.length > 0 ? (
        <ul
          className={cn("divide-y rounded-lg border", list.isPlaceholderData && "opacity-60")}
          aria-busy={list.isFetching}
        >
          {list.data.items.map((notification) => (
            <li key={notification.id}>
              <NotificationLink
                notification={notification}
                onFollow={(followed) => {
                  if (followed.read_at === null) one.mutate(followed.id);
                }}
              />
            </li>
          ))}
        </ul>
      ) : null}

      {list.data ? (
        <Pager
          page={list.data.page}
          pageSize={list.data.page_size}
          total={list.data.total}
          onPage={setPage}
        />
      ) : null}
    </div>
  );
}
