"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, CircleCheck, CircleX, Clock, Loader2, Play } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { CourseCover } from "@/components/courses/course-cover";
import { Mascot } from "@/components/mascot/mascot";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton, SkeletonRegion, SkeletonText } from "@/components/ui/skeleton";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { getOrder, type Order } from "@/lib/api/orders";
import { useAuth } from "@/lib/auth/auth-provider";
import { readItem, writeItem } from "@/lib/gamification/seen";
import { orderHeadline, orderSeenKey, shouldReact, type OrderTone } from "@/lib/commerce/order-view";
import { formatAmount, formatDateTime, formatDuration, formatPrice } from "@/lib/format";
import { cn } from "@/lib/utils";

/** How long to keep asking while the gateway's callback is still on its way. */
const POLL_MS = 3000;
const POLL_FOR_MS = 90_000;

/**
 * "Kết quả thanh toán" — what happened to one order.
 *
 * The page is reached by a redirect from the bank, whose query string says how
 * it went. That string is **not** what is shown: it arrives through a browser,
 * and a browser is something its owner can edit, so anyone could land here with
 * `vnp_ResponseCode=00` typed by hand. All that is taken from it is the order
 * code; the status comes from our own API, which only ever learns about a
 * payment from VNPay's server-to-server callback.
 *
 * That callback can also arrive a moment *after* the redirect, so a pending
 * order is polled for a minute and a half rather than declared failed.
 */
export function OrderResult({ code }: { code: string | null }) {
  const { accessToken, status } = useAuth();
  // Set once a pending order has been asked about for POLL_FOR_MS; "Kiểm tra
  // lại" clears it and starts the minute and a half again.
  const [gaveUp, setGaveUp] = useState(false);

  const order = useQuery({
    queryKey: ["order", code],
    queryFn: () => getOrder(accessToken as string, code as string),
    enabled: code !== null && status === "authenticated" && accessToken !== null,
    retry: false,
    refetchInterval: (query) => {
      const data = query.state.data as Order | undefined;
      if (data && data.status !== "pending") return false;
      return gaveUp ? false : POLL_MS;
    },
  });

  const pending = order.data?.status === "pending";
  useEffect(() => {
    if (!pending || gaveUp) return;
    const timer = window.setTimeout(() => setGaveUp(true), POLL_FOR_MS);
    return () => window.clearTimeout(timer);
  }, [pending, gaveUp]);

  // The callback that paid the order also enrolled the buyer and took the
  // bought lines out of their cart -- on the server, while this page waited.
  // What the header badge and the course pages cached before the trip to the
  // bank is now wrong, and nothing else here would ever refetch it.
  const queryClient = useQueryClient();
  const paid = order.data?.status === "paid";
  useEffect(() => {
    if (!paid) return;
    queryClient.invalidateQueries({ queryKey: ["cart"] });
    queryClient.invalidateQueries({ queryKey: ["my-enrollments"] });
    queryClient.invalidateQueries({ queryKey: ["enrollment"] });
  }, [paid, queryClient]);

  if (code === null) {
    return (
      <Alert variant="destructive">
        <AlertDescription>
          Liên kết này không kèm mã đơn hàng nên không tra cứu được.{" "}
          <Link href="/gio-hang" className="font-semibold underline underline-offset-4">
            Quay lại giỏ hàng
          </Link>
          .
        </AlertDescription>
      </Alert>
    );
  }

  if (status === "anonymous") {
    return (
      <div className="flex flex-col items-start gap-3 rounded-lg border bg-card p-6 sm:p-8">
        <h2 className="text-h2">Đăng nhập để xem đơn hàng</h2>
        <p className="max-w-prose text-body text-muted-foreground">
          Đơn hàng gắn với tài khoản đã đặt nó, kể cả khi bạn quay lại từ ngân hàng ở trình duyệt khác.
        </p>
        <Button asChild>
          <Link href={`/dang-nhap?next=${encodeURIComponent(`/thanh-toan/ket-qua?ma=${code}`)}`}>Đăng nhập</Link>
        </Button>
      </div>
    );
  }

  if (order.isError) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{apiErrorMessage(order.error)}</AlertDescription>
      </Alert>
    );
  }

  if (!order.data) return <OrderSkeleton />;

  return (
    <Receipt
      // A new status is a new screen: Naomi decides again whether to react.
      key={order.data.status}
      order={order.data}
      waiting={pending && !gaveUp}
      onCheckAgain={() => {
        setGaveUp(false);
        void order.refetch();
      }}
      checking={order.isFetching}
    />
  );
}

const HERO: Record<OrderTone, string> = {
  success: "bg-success-soft",
  warning: "border bg-card",
  destructive: "border bg-card",
  muted: "border bg-card",
};

const EYEBROW: Record<OrderTone, string> = {
  success: "text-success-text",
  warning: "text-warning-text",
  destructive: "text-destructive-text",
  muted: "text-muted-foreground",
};

function Receipt({
  order,
  waiting,
  onCheckAgain,
  checking,
}: {
  order: Order;
  waiting: boolean;
  onCheckAgain: () => void;
  checking: boolean;
}) {
  // A 0 đ order is settled at checkout and never sees a gateway: it was not
  // "paid", and its reference is its own code, not a VNPay transaction.
  const free = order.payment_provider === "none";
  const head = orderHeadline({
    status: order.status,
    free,
    itemCount: order.items.length,
    failureCode: order.failure_code,
    waiting,
  });

  // Decided once, when this screen first shows the outcome (see `shouldReact`).
  const [react] = useState(() =>
    shouldReact(order.status, readItem("local", orderSeenKey(order.code)), order.created_at, Date.now()),
  );
  useEffect(() => {
    if (order.status === "paid" || order.status === "failed") {
      writeItem("local", orderSeenKey(order.code), order.status);
    }
  }, [order.code, order.status]);

  const Icon = order.status === "paid" ? CircleCheck : order.status === "pending" ? Clock : CircleX;

  return (
    <div className="grid items-start gap-8 lg:grid-cols-[minmax(0,1fr)_23.75rem]">
      <div className="flex min-w-0 flex-col gap-6">
        <section
          aria-labelledby="order-title"
          className={cn(
            "@container flex flex-col items-center gap-4 rounded-xl px-5 py-6 text-center sm:px-8 sm:py-8",
            "@xl:flex-row @xl:items-center @xl:gap-8 @xl:text-left",
            HERO[head.tone],
          )}
        >
          {head.mood ? (
            <Mascot
              mood={head.mood}
              size="lg"
              event={react ? `${order.code}:${order.status}` : null}
              className="size-32 shrink-0 @xl:size-50"
            />
          ) : (
            <span className="flex size-14 shrink-0 items-center justify-center rounded-full bg-warning-soft text-warning-text">
              <Clock className="size-7" aria-hidden />
            </span>
          )}

          <div className="flex min-w-0 flex-col items-center gap-2 @xl:items-start">
            <p className={cn("inline-flex items-center gap-1.5 text-eyebrow uppercase", EYEBROW[head.tone])}>
              {/* Still asking the API: the eyebrow's clock turns into a spinner. */}
              {waiting ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Icon className="size-4" aria-hidden />}
              {head.eyebrow}
            </p>
            <h2 id="order-title" className="text-h1 text-balance @xl:text-display">
              {head.title}
            </h2>
            {/* The page waits here while the bank answers: say each change aloud. */}
            <p role="status" className="max-w-prose text-body-lg text-foreground/85">
              {head.description}
            </p>
            {head.reassurance ? <p className="max-w-prose text-body text-muted-foreground">{head.reassurance}</p> : null}


            <Actions order={order} waiting={waiting} onCheckAgain={onCheckAgain} checking={checking} />
          </div>
        </section>

        {order.status === "paid" ? <Bought order={order} /> : null}
      </div>

      <Details order={order} free={free} />
    </div>
  );
}

function Actions({
  order,
  waiting,
  onCheckAgain,
  checking,
}: {
  order: Order;
  waiting: boolean;
  onCheckAgain: () => void;
  checking: boolean;
}) {
  if (waiting) return null;

  const first = order.items[0]?.course;
  const buttons =
    order.status === "paid" ? (
      <>
        <Button size="lg" asChild>
          <Link href={first ? `/hoc/${first.slug}` : "/khoa-hoc-cua-toi"}>
            Vào học ngay
            <ArrowRight data-icon="inline-end" aria-hidden />
          </Link>
        </Button>
        <Button size="lg" variant="outline" asChild>
          <Link href="/khoa-hoc-cua-toi">Khóa học của tôi</Link>
        </Button>
      </>
    ) : order.status === "pending" ? (
      <>
        <Button size="lg" onClick={onCheckAgain} disabled={checking}>
          Kiểm tra lại
        </Button>
        <Button size="lg" variant="outline" asChild>
          <Link href="/khoa-hoc-cua-toi">Khóa học của tôi</Link>
        </Button>
      </>
    ) : (
      <>
        <Button size="lg" asChild>
          <Link href="/gio-hang">Quay lại giỏ hàng</Link>
        </Button>
        <Button size="lg" variant="outline" asChild>
          <Link href="/khoa-hoc">Xem khóa học khác</Link>
        </Button>
      </>
    );

  return <div className="mt-3 flex w-full flex-col gap-2 sm:w-auto sm:flex-row sm:flex-wrap">{buttons}</div>;
}

/** "Khóa học vừa mua": each one a click from its first lesson. */
function Bought({ order }: { order: Order }) {
  return (
    <section aria-labelledby="bought" className="flex flex-col gap-3">
      <h2 id="bought" className="text-title">
        Khóa học vừa mua
      </h2>
      <ul className="divide-y overflow-hidden rounded-lg border bg-card">
        {order.items.map(({ course }) => {
          const facts = [course.instructor.full_name, formatDuration(course.duration_total_s)].filter(Boolean);
          return (
            <li key={course.id} className="flex items-center gap-3 p-4 sm:gap-4 sm:px-5">
              <CourseCover
                thumbnailUrl={course.thumbnail_url}
                colorKey={course.id}
                size="xs"
                className="hidden w-28 shrink-0 rounded-sm sm:flex"
              />
              <div className="min-w-0 flex-1">
                <p className="text-title">{course.title}</p>
                <p className="text-body-sm text-muted-foreground">{facts.join(" · ")}</p>
              </div>
              <Button variant="secondary" className="shrink-0" asChild>
                <Link href={`/hoc/${course.slug}`} aria-label={`Bắt đầu học ${course.title}`}>
                  <Play className="fill-current" aria-hidden />
                  <span className="hidden sm:inline">Bắt đầu học</span>
                  <span className="sm:hidden">Học</span>
                </Link>
              </Button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

/** The receipt: codes, lines, and what was (or would have been) paid. */
function Details({ order, free }: { order: Order; free: boolean }) {
  const paid = order.status === "paid";
  return (
    <aside aria-labelledby="order-details" className="flex flex-col gap-4 rounded-lg border bg-card p-5 sm:p-6">
      <h2 id="order-details" className="text-title">
        {paid ? "Biên nhận" : "Đơn hàng"}
      </h2>

      <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-2 text-body-sm">
        <dt className="text-muted-foreground">Mã đơn</dt>
        <dd className="text-right font-mono font-medium break-all">{order.code}</dd>
        {order.provider_txn_id && !free ? (
          <>
            <dt className="text-muted-foreground">Mã giao dịch VNPay</dt>
            <dd className="text-right font-mono font-medium break-all">{order.provider_txn_id}</dd>
          </>
        ) : null}
        {order.paid_at ? (
          <>
            <dt className="text-muted-foreground">{free ? "Nhận lúc" : "Thanh toán lúc"}</dt>
            <dd className="text-right">{formatDateTime(order.paid_at)}</dd>
          </>
        ) : (
          <>
            <dt className="text-muted-foreground">Đặt lúc</dt>
            <dd className="text-right">{formatDateTime(order.created_at)}</dd>
          </>
        )}
        {order.status === "failed" && order.failure_code ? (
          <>
            <dt className="text-muted-foreground">Mã từ chối</dt>
            <dd className="text-right font-mono text-destructive-text">{order.failure_code}</dd>
          </>
        ) : null}
      </dl>

      <ul className="flex flex-col gap-2 border-t pt-3 text-body-sm">
        {order.items.map((item) => (
          <li key={item.course.id} className="flex justify-between gap-3">
            <Link href={`/khoa-hoc/${item.course.slug}`} className="min-w-0 hover:underline">
              {item.course.title}
            </Link>
            <span className="shrink-0 tabular-nums">{formatPrice(item.unit_price)}</span>
          </li>
        ))}
      </ul>

      <dl className="flex flex-col gap-1.5 border-t pt-3 text-body-sm tabular-nums">
        <div className="flex justify-between gap-3">
          <dt className="text-muted-foreground">Tạm tính</dt>
          <dd>{formatAmount(order.subtotal)}</dd>
        </div>
        {Number(order.discount) > 0 ? (
          <div className="flex justify-between gap-3 font-medium text-success-text">
            <dt>Giảm giá{order.coupon_code ? ` · ${order.coupon_code}` : ""}</dt>
            <dd>−{formatAmount(order.discount)}</dd>
          </div>
        ) : null}
        <div className="mt-1 flex items-baseline justify-between gap-3">
          <dt className="text-body font-semibold">{paid ? "Đã trả" : "Tổng cộng"}</dt>
          <dd className="text-h2">{formatAmount(order.total)}</dd>
        </div>
      </dl>

      <p className="text-caption font-normal text-muted-foreground">Cần hỏi về đơn này? Gửi kèm mã đơn ở trên.</p>
    </aside>
  );
}

/** The result on its way: the heading block and the receipt card. */
function OrderSkeleton() {
  return (
    <SkeletonRegion
      label="Đang tải đơn hàng…"
      className="grid items-start gap-8 lg:grid-cols-[minmax(0,1fr)_23.75rem]"
    >
      <div className="flex flex-col items-center gap-4 rounded-xl border px-5 py-6 sm:px-8 sm:py-8 lg:flex-row lg:gap-8">
        <Skeleton className="size-32 shrink-0 rounded-full lg:size-50" />
        <div className="flex w-full flex-col gap-2">
          <SkeletonText size="caption" className="w-24" />
          <Skeleton className="h-10 w-3/4" />
          <SkeletonText className="w-full" />
          <Skeleton className="mt-3 h-11 w-40" />
        </div>
      </div>
      <div className="flex flex-col gap-4 rounded-lg border p-5 sm:p-6">
        <SkeletonText size="title" className="w-24" />
        <SkeletonText size="body-sm" className="w-full" />
        <SkeletonText size="body-sm" className="w-full" />
        <SkeletonText size="body-sm" className="w-2/3" />
        <Skeleton className="h-8 w-full" />
      </div>
    </SkeletonRegion>
  );
}
