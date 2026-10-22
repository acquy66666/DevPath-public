"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { CouponBox } from "@/components/commerce/coupon-box";
import { CourseCover } from "@/components/courses/course-cover";
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
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton, SkeletonRegion, SkeletonText } from "@/components/ui/skeleton";
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
import { nothingToPay, settledOrderPath } from "@/lib/commerce/checkout";
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
  const router = useRouter();
  const checkout = useMutation({
    mutationFn: async () => {
      const order = await createOrder(accessToken as string, couponCode);
      setOrderCode(order.code);
      // A 0 đ order comes back already paid: no gateway, no payment URL.
      const settled = settledOrderPath(order);
      if (settled) return { href: settled, gateway: false };
      return {
        href: await createPaymentUrl(accessToken as string, order.code),
        gateway: true,
      };
    },
    onSuccess: ({ href, gateway }) => {
      if (gateway) {
        // A full navigation rather than the router: the destination is
        // VNPay, which is not this app.
        window.location.href = href;
        return;
      }
      router.push(href);
    },
  });

  if (status === "loading") {
    return <CartSkeleton />;
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
    return <CartSkeleton />;
  }

  if (cart.data.items.length === 0) {
    return (
      <EmptyState
        mood="empty-cart"
        title="Giỏ hàng đang trống"
        description="Thêm khóa học bạn muốn mua vào đây, rồi thanh toán một lần."
        action={
          <Button asChild>
            <Link href="/khoa-hoc">Tìm khóa học</Link>
          </Button>
        }
      />
    );
  }

  const owned = cart.data.items.filter((item) => item.already_enrolled);
  const discount = coupon.data ?? null;
  // What pressing the button will cost: the total, and the button's words.
  const amountDue = discount ? discount.total : cart.data.total;

  return (
    <div className="grid gap-8 lg:grid-cols-[1fr_20rem]">
      <div className="space-y-4">
        {remove.isError ? (
          <Alert variant="destructive">
            <AlertDescription>{apiErrorMessage(remove.error)}</AlertDescription>
          </Alert>
        ) : null}

        <p className="text-muted-foreground">{cart.data.items.length} khóa học</p>

        <ul className="divide-y rounded-lg border">
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
              {formatPrice(amountDue)}
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
              {nothingToPay(amountDue)
                ? "Nhận khóa học"
                : "Thanh toán qua VNPay"}
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
              {nothingToPay(amountDue)
                ? "Đơn 0đ: khóa học vào tài khoản ngay, không qua trang thanh toán."
                : "Bạn sẽ được chuyển sang trang thanh toán của VNPay."}
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

  const price = (
    <span
      className={
        item.already_enrolled
          ? "font-semibold text-muted-foreground line-through"
          : "font-semibold"
      }
    >
      {formatPrice(course.price)}
    </span>
  );
  const removeButton = (
    <Button
      variant="ghost"
      size="sm"
      onClick={onRemove}
      disabled={removing}
      aria-label={`Bỏ ${course.title} khỏi giỏ hàng`}
    >
      {removing ? <Loader2 className="animate-spin" aria-hidden /> : <Trash2 aria-hidden />}
      Bỏ
    </Button>
  );

  return (
    <div className="flex items-start gap-3 p-4 sm:gap-4">
      <Link
        href={`/khoa-hoc/${course.slug}`}
        className="shrink-0"
        aria-label={course.title}
      >
        <CourseCover
          thumbnailUrl={course.thumbnail_url}
          colorKey={course.id}
          size="sm"
          className="w-24 rounded-md sm:w-40"
        />
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

        {/* On a phone the price goes under the title: a third column there
            left the title a word per line. */}
        <div className="mt-2 flex items-center justify-between gap-2 sm:hidden">
          {price}
          {removeButton}
        </div>
      </div>

      <div className="hidden shrink-0 flex-col items-end gap-2 sm:flex">
        {price}
        {removeButton}
      </div>
    </div>
  );
}

/**
 * The cart on its way: the count, one line of the list (cover, title,
 * instructor, price and "Bỏ"), the "Xóa toàn bộ" button and the summary card,
 * where the real ones go.
 */
function CartSkeleton() {
  return (
    <SkeletonRegion label="Đang tải giỏ hàng…" className="grid gap-8 lg:grid-cols-[1fr_20rem]">
      <div className="space-y-4">
        <SkeletonText className="w-24" />
        <div className="flex items-start gap-3 rounded-lg border p-4 sm:gap-4">
          <Skeleton className="aspect-video w-24 shrink-0 sm:w-40" />
          <div className="min-w-0 flex-1">
            <SkeletonText className="w-3/4" />
            <SkeletonText size="body-sm" className="w-1/3" />
            <div className="mt-2 flex items-center justify-between gap-2 sm:hidden">
              <SkeletonText className="w-20" />
              <Skeleton className="h-8 w-16" />
            </div>
          </div>
          <div className="hidden shrink-0 flex-col items-end gap-2 sm:flex">
            <SkeletonText className="w-20" />
            <Skeleton className="h-8 w-16" />
          </div>
        </div>
        <Skeleton className="h-8 w-44" />
      </div>
      <div className="flex flex-col gap-4 rounded-lg border bg-card py-4">
        <div className="space-y-1 px-4">
          <SkeletonText size="body-sm" className="w-20" />
          <Skeleton className="h-9 w-40" />
        </div>
        <div className="space-y-3 px-4">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-9 w-full" />
          <SkeletonText size="caption" className="h-4" />
        </div>
      </div>
    </SkeletonRegion>
  );
}
