"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { GraduationCap, Loader2, Trash2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { CouponBox } from "@/components/commerce/coupon-box";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  applyCoupon,
  clearCart,
  getCart,
  removeFromCart,
  type Cart,
  type CartItem,
} from "@/lib/api/commerce";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { createOrder, createPaymentUrl } from "@/lib/api/orders";
import { useAuth } from "@/lib/auth/auth-provider";
import { formatAmount, formatPrice } from "@/lib/format";

/**
 * "Giỏ hàng".
 *
 * Guarded here rather than in middleware, for the same reason as "Khóa học của
 * tôi": the session lives in a cookie on the backend's origin, which Next's
 * middleware cannot read. The real protection is the API — `/cart` answers 401
 * without a token, whatever this component decides to draw.
 */
export function CartView() {
  const { accessToken, status } = useAuth();
  const queryClient = useQueryClient();
  const [couponCode, setCouponCode] = useState<string | null>(null);

  const cart = useQuery({
    queryKey: ["cart"],
    queryFn: () => getCart(accessToken as string),
    enabled: status === "authenticated" && accessToken !== null,
  });

  // What a coupon is answered against: which courses are in the cart and what
  // they come to. Both are part of the key, so taking a course out asks the
  // question again instead of leaving a discount on screen that the backend
  // would now refuse -- and a code that no longer applies says so in the box.
  const cartShape = cart.data
    ? `${cart.data.items.map((item) => item.course.id).join(",")}|${cart.data.total}`
    : "";

  const coupon = useQuery({
    queryKey: ["cart-coupon", couponCode, cartShape],
    queryFn: () => applyCoupon(accessToken as string, couponCode as string),
    enabled: couponCode !== null && accessToken !== null && cart.data !== undefined,
    // A refused code is an answer, not a hiccup: retrying it three times only
    // makes the same sentence arrive later.
    retry: false,
  });

  const remove = useMutation({
    mutationFn: (courseId: string) =>
      removeFromCart(accessToken as string, courseId),
    onSuccess: (updated: Cart) => queryClient.setQueryData(["cart"], updated),
  });

  const empty = useMutation({
    mutationFn: () => clearCart(accessToken as string),
    // 204 carries nothing to write into the cache, so this one refetches.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["cart"] }),
  });

  // Two requests, on purpose. The order is a record of what is being bought
  // and survives whatever happens next; the payment URL is a signed string
  // with a few minutes' life. Keeping the code of the order that was created
  // means a server with no VNPay credentials can still say "đơn đã tạo, đây"
  // instead of losing it behind an error.
  const [orderCode, setOrderCode] = useState<string | null>(null);
  const checkout = useMutation({
    mutationFn: async () => {
      const order = await createOrder(accessToken as string, couponCode);
      setOrderCode(order.code);
      return createPaymentUrl(accessToken as string, order.code);
    },
    onSuccess: (url: string) => {
      // A full navigation rather than the router: the destination is VNPay,
      // which is not this app.
      window.location.href = url;
    },
  });

  if (status === "loading") {
    return <div className="h-64 animate-pulse rounded-xl border bg-muted/40" />;
  }

  if (status === "anonymous") {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Đăng nhập để xem giỏ hàng</CardTitle>
          <CardDescription>
            Giỏ hàng gắn với tài khoản nên bạn mở được trên mọi thiết bị.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button asChild>
            <Link href="/dang-nhap?next=/gio-hang">Đăng nhập</Link>
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (cart.isError) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{apiErrorMessage(cart.error)}</AlertDescription>
      </Alert>
    );
  }

  if (!cart.data) {
    return <div className="h-64 animate-pulse rounded-xl border bg-muted/40" />;
  }

  if (cart.data.items.length === 0) {
    return (
      <div className="rounded-xl border border-dashed p-12 text-center">
        <p className="font-medium">Giỏ hàng đang trống</p>
        <p className="mt-1 text-sm text-muted-foreground">
          Thêm khóa học bạn muốn mua vào đây, rồi thanh toán một lần.
        </p>
        <Button className="mt-4" asChild>
          <Link href="/khoa-hoc">Tìm khóa học</Link>
        </Button>
      </div>
    );
  }

  const owned = cart.data.items.filter((item) => item.already_enrolled);
  const discount = coupon.data ?? null;

  return (
    <div className="grid gap-8 lg:grid-cols-[1fr_20rem]">
      <div className="space-y-4">
        {remove.isError ? (
          <Alert variant="destructive">
            <AlertDescription>{apiErrorMessage(remove.error)}</AlertDescription>
          </Alert>
        ) : null}

        <p className="text-muted-foreground">{cart.data.items.length} khóa học</p>

        <ul className="divide-y rounded-xl border">
          {cart.data.items.map((item) => (
            <li key={item.course.id}>
              <CartRow
                item={item}
                // Only worth marking for a coupon that covers *some* lines. A
                // site-wide one covers them all, and a badge on every row says
                // nothing while taking up the space that tells the reader
                // which lines are already theirs.
                discounted={
                  discount?.coupon.scope === "courses" &&
                  discount.course_ids.includes(item.course.id)
                }
                onRemove={() => remove.mutate(item.course.id)}
                removing={remove.isPending && remove.variables === item.course.id}
              />
            </li>
          ))}
        </ul>

        <Button
          variant="ghost"
          size="sm"
          onClick={() => empty.mutate()}
          disabled={empty.isPending}
        >
          {empty.isPending ? "Đang xóa…" : "Xóa toàn bộ giỏ hàng"}
        </Button>
      </div>

      <aside className="lg:sticky lg:top-6 lg:self-start">
        <Card>
          <CardHeader>
            <CardDescription>Tổng cộng</CardDescription>
            <CardTitle className="text-3xl">
              {formatPrice(discount ? discount.total : cart.data.total)}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {discount ? (
              <dl className="space-y-1 text-sm">
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Tạm tính</dt>
                  <dd>{formatAmount(discount.subtotal)}</dd>
                </div>
                <div className="flex justify-between font-medium text-emerald-700">
                  <dt>Giảm giá</dt>
                  <dd>−{formatAmount(discount.discount)}</dd>
                </div>
              </dl>
            ) : null}

            <CouponBox
              discount={discount}
              pending={coupon.isFetching}
              error={coupon.error}
              onApply={setCouponCode}
              onClear={() => setCouponCode(null)}
            />

            {owned.length > 0 ? (
              <p className="text-xs text-muted-foreground">
                {owned.length} khóa học bạn đã có không được tính vào số tiền này.
              </p>
            ) : null}

            <Button
              className="w-full"
              onClick={() => checkout.mutate()}
              disabled={checkout.isPending}
            >
              {checkout.isPending ? (
                <Loader2 className="animate-spin" aria-hidden />
              ) : null}
              Thanh toán qua VNPay
            </Button>

            {checkout.isError ? (
              <Alert variant="destructive">
                <AlertDescription>
                  {apiErrorMessage(checkout.error)}
                  {orderCode ? (
                    <>
                      {" "}
                      Đơn hàng <span className="font-medium">{orderCode}</span>{" "}
                      đã được tạo —{" "}
                      <Link
                        href={`/thanh-toan/ket-qua?ma=${orderCode}`}
                        className="underline underline-offset-4"
                      >
                        xem đơn
                      </Link>
                      .
                    </>
                  ) : null}
                </AlertDescription>
              </Alert>
            ) : null}

            <p className="text-center text-xs text-muted-foreground">
              Bạn sẽ được chuyển sang trang thanh toán của VNPay.
            </p>
          </CardContent>
        </Card>
      </aside>
    </div>
  );
}

/** One line of the cart: the course, its price, and a way to take it out. */
function CartRow({
  item,
  discounted,
  onRemove,
  removing,
}: {
  item: CartItem;
  /** Covered by the applied coupon, which only covers part of this cart. */
  discounted: boolean;
  onRemove: () => void;
  removing: boolean;
}) {
  const { course } = item;

  return (
    <div className="flex items-start gap-4 p-4">
      <Link
        href={`/khoa-hoc/${course.slug}`}
        className="shrink-0"
        aria-label={course.title}
      >
        {course.thumbnail_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={course.thumbnail_url}
            alt=""
            className="aspect-video w-32 rounded-lg bg-muted object-cover sm:w-40"
          />
        ) : (
          <div className="flex aspect-video w-32 items-center justify-center rounded-lg bg-muted sm:w-40">
            <GraduationCap className="size-6 text-muted-foreground" aria-hidden />
          </div>
        )}
      </Link>

      <div className="min-w-0 flex-1">
        <Link
          href={`/khoa-hoc/${course.slug}`}
          className="font-medium hover:underline"
        >
          {course.title}
        </Link>
        <p className="text-sm text-muted-foreground">{course.instructor.full_name}</p>

        {discounted ? (
          <Badge variant="secondary" className="mt-1">
            Đang được giảm giá
          </Badge>
        ) : null}

        {item.already_enrolled ? (
          <p className="mt-1 text-xs text-muted-foreground">
            Bạn đã có khóa học này —{" "}
            <Link href={`/hoc/${course.slug}`} className="underline underline-offset-4">
              vào học
            </Link>
            . Khóa học này không bị tính tiền.
          </p>
        ) : null}
      </div>

      <div className="flex shrink-0 flex-col items-end gap-2">
        <span
          className={
            item.already_enrolled
              ? "font-semibold text-muted-foreground line-through"
              : "font-semibold"
          }
        >
          {formatPrice(course.price)}
        </span>
        <Button
          variant="ghost"
          size="sm"
          onClick={onRemove}
          disabled={removing}
          aria-label={`Bỏ ${course.title} khỏi giỏ hàng`}
        >
          {removing ? (
            <Loader2 className="animate-spin" aria-hidden />
          ) : (
            <Trash2 aria-hidden />
          )}
          Bỏ
        </Button>
      </div>
    </div>
  );
}
