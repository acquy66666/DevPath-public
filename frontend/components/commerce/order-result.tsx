"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Clock, XCircle } from "lucide-react";
import Link from "next/link";
import { useEffect } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { getOrder, type Order } from "@/lib/api/orders";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { useAuth } from "@/lib/auth/auth-provider";
import { formatAmount, formatPrice } from "@/lib/format";

/** VNPay's refusal codes, in words. Anything else falls back to the code. */
const REFUSALS: Record<string, string> = {
  "07": "Giao dịch bị nghi ngờ gian lận nên ngân hàng đã giữ lại.",
  "09": "Thẻ chưa đăng ký dịch vụ InternetBanking.",
  "10": "Xác thực thông tin thẻ sai quá 3 lần.",
  "11": "Đã hết hạn chờ thanh toán.",
  "12": "Thẻ hoặc tài khoản đang bị khóa.",
  "24": "Bạn đã hủy giao dịch.",
  "51": "Tài khoản không đủ số dư.",
  "65": "Tài khoản đã vượt hạn mức giao dịch trong ngày.",
  "75": "Ngân hàng đang bảo trì.",
  "79": "Sai mật khẩu thanh toán quá số lần cho phép.",
};

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

  const order = useQuery({
    queryKey: ["order", code],
    queryFn: () => getOrder(accessToken as string, code as string),
    enabled: code !== null && status === "authenticated" && accessToken !== null,
    retry: false,
    refetchInterval: (query) => {
      const data = query.state.data as Order | undefined;
      if (data && data.status !== "pending") return false;
      // `dataUpdatedAt` is 0 until the first answer arrives, so this is the
      // age of the answer rather than of the page — a callback that takes two
      // minutes stops being waited for, and the page says what to do then.
      const since = Date.now() - (query.state.dataUpdatedAt || Date.now());
      return since < POLL_FOR_MS ? POLL_MS : false;
    },
  });

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
          <Link href="/gio-hang" className="underline underline-offset-4">
            Quay lại giỏ hàng
          </Link>
          .
        </AlertDescription>
      </Alert>
    );
  }

  if (status === "anonymous") {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Đăng nhập để xem đơn hàng</CardTitle>
          <CardDescription>
            Đơn hàng gắn với tài khoản đã đặt nó, kể cả khi bạn quay lại từ ngân
            hàng ở trình duyệt khác.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button asChild>
            <Link href={`/dang-nhap?next=/thanh-toan/ket-qua?ma=${code}`}>
              Đăng nhập
            </Link>
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (order.isError) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{apiErrorMessage(order.error)}</AlertDescription>
      </Alert>
    );
  }

  if (!order.data) {
    return <div className="h-64 animate-pulse rounded-xl border bg-muted/40" />;
  }

  return <Receipt order={order.data} waiting={order.isFetching} />;
}

function Receipt({ order, waiting }: { order: Order; waiting: boolean }) {
  const heading = {
    paid: {
      icon: <CheckCircle2 className="size-8 text-emerald-600" aria-hidden />,
      title: "Thanh toán thành công",
      description: "Các khóa học trong đơn đã vào tài khoản của bạn.",
    },
    pending: {
      icon: <Clock className="size-8 text-amber-600" aria-hidden />,
      title: "Đang chờ xác nhận",
      description:
        "Ngân hàng chưa báo kết quả về. Trang này tự cập nhật, bạn không cần tải lại.",
    },
    failed: {
      icon: <XCircle className="size-8 text-destructive" aria-hidden />,
      title: "Thanh toán không thành công",
      description:
        order.failure_code && REFUSALS[order.failure_code]
          ? REFUSALS[order.failure_code]
          : "Chưa có khoản nào bị trừ. Bạn thử lại hoặc chọn cách thanh toán khác nhé.",
    },
    cancelled: {
      icon: <XCircle className="size-8 text-muted-foreground" aria-hidden />,
      title: "Đơn hàng đã hủy",
      description: "Giỏ hàng của bạn vẫn còn nguyên.",
    },
  }[order.status];

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex items-start gap-3">
            {heading.icon}
            <div>
              <CardTitle className="text-2xl">{heading.title}</CardTitle>
              <CardDescription>{heading.description}</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <dl className="grid gap-1 text-sm sm:grid-cols-2">
            <div className="flex justify-between sm:block">
              <dt className="text-muted-foreground">Mã đơn hàng</dt>
              <dd className="font-medium">{order.code}</dd>
            </div>
            {order.provider_txn_id ? (
              <div className="flex justify-between sm:block">
                <dt className="text-muted-foreground">Mã giao dịch VNPay</dt>
                <dd className="font-medium">{order.provider_txn_id}</dd>
              </div>
            ) : null}
          </dl>

          <div className="flex flex-wrap gap-3">
            {order.status === "paid" ? (
              <Button asChild>
                <Link href="/khoa-hoc-cua-toi">Vào học ngay</Link>
              </Button>
            ) : null}
            {order.status === "failed" || order.status === "cancelled" ? (
              <Button asChild>
                <Link href="/gio-hang">Quay lại giỏ hàng</Link>
              </Button>
            ) : null}
            {order.status === "pending" && !waiting ? (
              <p className="text-sm text-muted-foreground">
                Quá lâu chưa có kết quả? Mã đơn hàng ở trên là thứ cần gửi cho
                chúng mình khi hỏi lại.
              </p>
            ) : null}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Chi tiết đơn hàng</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <ul className="divide-y">
            {order.items.map((item) => (
              <li
                key={item.course.id}
                className="flex items-start justify-between gap-4 py-3"
              >
                <div className="min-w-0">
                  <Link
                    href={`/khoa-hoc/${item.course.slug}`}
                    className="font-medium hover:underline"
                  >
                    {item.course.title}
                  </Link>
                  <p className="text-sm text-muted-foreground">
                    {item.course.instructor.full_name}
                  </p>
                </div>
                <span className="shrink-0 font-medium">
                  {formatPrice(item.unit_price)}
                </span>
              </li>
            ))}
          </ul>

          <dl className="space-y-1 border-t pt-3 text-sm">
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Tạm tính</dt>
              <dd>{formatAmount(order.subtotal)}</dd>
            </div>
            {Number(order.discount) > 0 ? (
              <div className="flex justify-between text-emerald-700">
                <dt>Giảm giá {order.coupon_code ? `(${order.coupon_code})` : ""}</dt>
                <dd>−{formatAmount(order.discount)}</dd>
              </div>
            ) : null}
            <div className="flex justify-between text-base font-semibold">
              <dt>Tổng cộng</dt>
              <dd>{formatAmount(order.total)}</dd>
            </div>
          </dl>
        </CardContent>
      </Card>
    </div>
  );
}
