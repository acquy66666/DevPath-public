"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Check, Heart, Loader2, Lock, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { CouponBox } from "@/components/commerce/coupon-box";
import { useOwnedCourses } from "@/components/commerce/use-owned-courses";
import { CourseCover } from "@/components/courses/course-cover";
import { Mascot } from "@/components/mascot/mascot";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton, SkeletonRegion, SkeletonText } from "@/components/ui/skeleton";
import { toast } from "@/components/ui/toast";
import {
  addToCart,
  addToWishlist,
  applyCoupon,
  clearCart,
  getCart,
  listWishlist,
  removeFromCart,
  type Cart,
  type CartItem,
  type WishlistItem,
} from "@/lib/api/commerce";
import { LEVEL_LABELS } from "@/lib/courses/labels";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { createOrder, createPaymentUrl } from "@/lib/api/orders";
import { useAuth } from "@/lib/auth/auth-provider";
import { cartHeadline, payableCount, payLabel, payNote, wishlistPicks } from "@/lib/commerce/cart-view";
import { settledOrderPath } from "@/lib/commerce/checkout";
import { formatAmount, formatDuration, formatPrice } from "@/lib/format";

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
  const signedIn = status === "authenticated" && accessToken !== null;

  const cart = useQuery({
    queryKey: ["cart"],
    queryFn: () => getCart(accessToken as string),
    enabled: signedIn,
  });

  // The first page of saved courses, for "Trong danh sách yêu thích của bạn".
  // Same key as the wishlist page's first page, so one of them is free.
  const wishlist = useQuery({
    queryKey: ["wishlist", 1],
    queryFn: () => listWishlist(accessToken as string, 1),
    enabled: signedIn,
  });

  const saved = wishlist.data?.items ?? [];
  const ownership = useOwnedCourses(
    signedIn ? accessToken : null,
    saved.map((item) => item.course.id),
  );

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

  // The row leaves the list, so a toast says which course went and offers it
  // back: putting it in again is the same request as "Thêm vào giỏ".
  const remove = useMutation({
    mutationFn: (courseId: string) => removeFromCart(accessToken as string, courseId),
    onSuccess: (updated: Cart, courseId) => {
      const title = courseTitle(queryClient.getQueryData<Cart>(["cart"]), courseId);
      queryClient.setQueryData(["cart"], updated);
      toast({
        title: title ? `Đã bỏ “${title}” khỏi giỏ hàng` : "Đã bỏ khóa học khỏi giỏ hàng",
        action: {
          label: "Hoàn tác",
          altText: "Thêm lại khóa học vừa bỏ vào giỏ hàng",
          onSelect: () => add.mutate(courseId),
        },
      });
    },
  });

  // "Để dành sau": saved first, then taken out, so a failure halfway leaves
  // the course in the cart rather than nowhere.
  const saveForLater = useMutation({
    mutationFn: async (courseId: string) => {
      await addToWishlist(accessToken as string, courseId);
      return removeFromCart(accessToken as string, courseId);
    },
    onSuccess: (updated: Cart, courseId) => {
      const title = courseTitle(queryClient.getQueryData<Cart>(["cart"]), courseId);
      queryClient.setQueryData(["cart"], updated);
      queryClient.invalidateQueries({ queryKey: ["wishlist"] });
      queryClient.invalidateQueries({ queryKey: ["wishlist-ids"] });
      toast({
        title: title ? `Đã để dành “${title}”` : "Đã để dành khóa học",
        description: "Khóa học nằm trong danh sách yêu thích của bạn.",
      });
    },
  });

  const add = useMutation({
    mutationFn: (courseId: string) => addToCart(accessToken as string, courseId),
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

  if (status === "loading") return <CartSkeleton />;

  if (status === "anonymous") {
    return (
      <div className="@container rounded-lg border bg-card">
        <div className="flex flex-col items-center gap-4 px-6 py-10 text-center @md:flex-row @md:justify-center @md:gap-8 @md:px-10 @md:text-left">
          <Mascot mood="empty-cart" size="md" />
          <div className="flex min-w-0 flex-col items-center gap-1 @md:items-start">
            <h2 className="text-title text-foreground">Đăng nhập để xem giỏ hàng</h2>
            <p className="max-w-md text-body-sm text-muted-foreground">
              Giỏ hàng gắn với tài khoản nên bạn mở được trên mọi thiết bị.
            </p>
            <div className="mt-3 flex flex-wrap justify-center gap-2">
              <Button asChild>
                <Link href="/dang-nhap?next=/gio-hang">Đăng nhập</Link>
              </Button>
              <Button variant="outline" asChild>
                <Link href="/dang-ky?next=/gio-hang">Đăng ký miễn phí</Link>
              </Button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (cart.isError) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{apiErrorMessage(cart.error)}</AlertDescription>
      </Alert>
    );
  }

  if (!cart.data) return <CartSkeleton />;

  // Wait for ownership before offering anything: a course bought a minute ago
  // must not flash up with "Thêm vào giỏ".
  const picks = ownership.settled ? wishlistPicks(saved, cart.data.items, ownership.owned) : [];
  const fromWishlist =
    picks.length > 0 ? (
      <WishlistPicks
        picks={picks}
        onAdd={(courseId) => add.mutate(courseId)}
        adding={add.isPending ? (add.variables ?? null) : null}
        error={add.isError ? add.error : null}
      />
    ) : null;

  if (cart.data.items.length === 0) {
    return (
      <div className="space-y-8">
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
        {fromWishlist}
      </div>
    );
  }

  const items = cart.data.items;
  const discount = coupon.data ?? null;
  // What pressing the button will cost: the total, and the button's words.
  const amountDue = discount ? discount.total : cart.data.total;
  const subtotal = discount ? discount.subtotal : cart.data.total;
  const label = payLabel(amountDue, formatAmount(amountDue));
  const busy = checkout.isPending || checkout.isSuccess;

  const payButton = (className?: string, compact = false) => (
    <Button size="lg" className={className} onClick={() => checkout.mutate()} disabled={busy}>
      {busy ? (
        <>
          <Loader2 className="animate-spin" aria-hidden />
          {/* Success too: the browser is on its way to VNPay. */}
          {Number(amountDue) === 0 ? "Đang nhận khóa học…" : "Đang chuyển sang VNPay…"}
        </>
      ) : (
        <>
          {/* The phone bar shows the total beside the button already. */}
          {compact ? (Number(amountDue) === 0 ? "Nhận khóa học" : "Thanh toán qua VNPay") : label}
          <ArrowRight data-icon="inline-end" aria-hidden />
        </>
      )}
    </Button>
  );

  return (
    <div className="space-y-6">
      <p className="-mt-4 text-body text-muted-foreground">{cartHeadline(items)}</p>

      <div className="grid items-start gap-8 lg:grid-cols-[minmax(0,1fr)_22.5rem]">
        <div className="min-w-0 space-y-4">
          {remove.isError || saveForLater.isError ? (
            <Alert variant="destructive">
              <AlertDescription>
                {apiErrorMessage(remove.isError ? remove.error : saveForLater.error)}
              </AlertDescription>
            </Alert>
          ) : null}

          <ul className="divide-y overflow-hidden rounded-lg border bg-card">
            {items.map((item) => (
              <li key={item.course.id}>
                <CartRow
                  item={item}
                  // Only worth marking for a coupon that covers *some* lines. A
                  // site-wide one covers them all, and a mark on every row says
                  // nothing.
                  discounted={
                    discount?.coupon.scope === "courses" && discount.course_ids.includes(item.course.id)
                  }
                  onRemove={() => remove.mutate(item.course.id)}
                  onSave={() => saveForLater.mutate(item.course.id)}
                  pending={
                    (remove.isPending && remove.variables === item.course.id) ||
                    (saveForLater.isPending && saveForLater.variables === item.course.id)
                  }
                />
              </li>
            ))}
          </ul>

          <div className="flex justify-end">
            <Button
              variant="ghost"
              size="sm"
              className="text-muted-foreground"
              onClick={() => empty.mutate()}
              disabled={empty.isPending}
            >
              {empty.isPending ? "Đang xóa…" : "Xóa toàn bộ giỏ hàng"}
            </Button>
          </div>

          <div className="hidden lg:block">{fromWishlist}</div>
        </div>

        <aside
          aria-labelledby="cart-summary"
          className="flex flex-col gap-5 rounded-lg border bg-card p-5 shadow-md sm:p-6 lg:sticky lg:top-6"
        >
          <h2 id="cart-summary" className="text-title">
            Tóm tắt đơn hàng
          </h2>

          <dl className="flex flex-col gap-2 text-body tabular-nums">
            <div className="flex justify-between gap-4">
              <dt className="text-muted-foreground">
                Tạm tính · {payableCount(items)} khóa học
              </dt>
              <dd>{formatAmount(subtotal)}</dd>
            </div>
            {discount ? (
              <div className="flex justify-between gap-4 font-medium text-success-text">
                <dt>Giảm giá · {discount.coupon.code}</dt>
                <dd>−{formatAmount(discount.discount)}</dd>
              </div>
            ) : null}
            <div className="mt-1 flex items-baseline justify-between gap-4 border-t pt-3">
              <dt className="font-semibold">Tổng cộng</dt>
              <dd className="text-h1" data-testid="cart-total">
                {formatAmount(amountDue)}
              </dd>
            </div>
          </dl>

          <CouponBox
            discount={discount}
            pending={coupon.isFetching}
            error={coupon.error}
            onApply={setCouponCode}
            onClear={() => setCouponCode(null)}
          />

          <div className="flex flex-col gap-3">
            {/* On a phone the button lives in the bar at the bottom of the screen. */}
            {payButton("hidden w-full lg:flex")}
            <p className="flex gap-2 text-caption font-normal text-muted-foreground">
              <Lock className="mt-0.5 size-4 shrink-0" aria-hidden />
              <span>{payNote(amountDue)}</span>
            </p>
          </div>

          <CheckoutError error={checkout.isError ? checkout.error : null} orderCode={orderCode} />
        </aside>

        <div className="lg:hidden">{fromWishlist}</div>
      </div>

      {/* Below lg: the total and the button stay at the bottom of the screen
          while the list scrolls past. */}
      <div className="sticky bottom-0 z-10 -mx-4 flex items-center gap-3 border-t bg-card px-4 py-3 shadow-lg lg:hidden">
        <div className="shrink-0">
          <p className="text-caption font-normal text-muted-foreground">Tổng cộng</p>
          <p className="text-title tabular-nums">{formatAmount(amountDue)}</p>
        </div>
        {payButton("min-w-0 flex-1", true)}
      </div>
    </div>
  );
}

/** One line of the cart: the course, its price, and ways to take it out. */
/** The title of a course in the cart as it was before a change. */
function courseTitle(cart: Cart | undefined, courseId: string): string | null {
  return cart?.items.find((item) => item.course.id === courseId)?.course.title ?? null;
}

function CartRow({
  item,
  discounted,
  onRemove,
  onSave,
  pending,
}: {
  item: CartItem;
  /** Covered by the applied coupon, which only covers part of this cart. */
  discounted: boolean;
  onRemove: () => void;
  onSave: () => void;
  pending: boolean;
}) {
  const { course } = item;
  const owned = item.already_enrolled;
  const facts = [
    course.instructor.full_name,
    LEVEL_LABELS[course.level],
    formatDuration(course.duration_total_s),
  ].filter(Boolean);

  const price = owned ? (
    <p className="text-body text-muted-foreground tabular-nums line-through">{formatPrice(course.price)}</p>
  ) : (
    <p className="text-body-lg font-bold tabular-nums">{formatPrice(course.price)}</p>
  );

  return (
    <div className={owned ? "flex gap-3 bg-background p-4 sm:gap-4 sm:p-5" : "flex gap-3 p-4 sm:gap-4 sm:p-5"}>
      <Link
        href={`/khoa-hoc/${course.slug}`}
        className={owned ? "shrink-0 opacity-70" : "shrink-0"}
        aria-label={course.title}
      >
        <CourseCover
          thumbnailUrl={course.thumbnail_url}
          colorKey={course.id}
          size="sm"
          className="w-24 rounded-md sm:w-40"
        />
      </Link>

      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <div className="flex items-start justify-between gap-3">
          <Link
            href={`/khoa-hoc/${course.slug}`}
            className="text-title text-foreground hover:underline hover:underline-offset-4"
          >
            {course.title}
          </Link>
          <div className="hidden shrink-0 sm:block">{price}</div>
        </div>
        <p className="text-body-sm text-muted-foreground">{facts.join(" · ")}</p>

        {discounted ? (
          <p className="text-body-sm font-medium text-success-text">Được giảm theo mã đang áp dụng</p>
        ) : null}

        {owned ? (
          <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-body-sm text-muted-foreground">
            <span className="inline-flex items-center gap-1 rounded-full bg-success-soft px-2 py-0.5 text-caption text-success-text">
              <Check className="size-3.5" aria-hidden />
              Bạn đã có khóa này
            </span>
            <Link href={`/hoc/${course.slug}`} className="font-semibold text-link">
              Vào học
            </Link>
            <span aria-hidden>·</span>
            <button
              type="button"
              onClick={onRemove}
              disabled={pending}
              className="underline underline-offset-4 hover:text-foreground"
              aria-label={`Bỏ ${course.title} khỏi giỏ hàng`}
            >
              Bỏ khỏi giỏ
            </button>
            <span className="sr-only">Khóa học này không bị tính tiền.</span>
          </div>
        ) : (
          <div className="mt-auto flex flex-wrap items-center gap-1 pt-1">
            <div className="mr-auto sm:hidden">{price}</div>
            <Button
              variant="ghost"
              size="sm"
              onClick={onSave}
              disabled={pending}
              aria-label={`Để dành ${course.title} vào yêu thích`}
            >
              <Heart aria-hidden />
              Để dành sau
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={onRemove}
              disabled={pending}
              aria-label={`Bỏ ${course.title} khỏi giỏ hàng`}
            >
              {pending ? <Loader2 className="animate-spin" aria-hidden /> : <Trash2 aria-hidden />}
              Bỏ
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}

/** "Trong danh sách yêu thích của bạn": saved courses one click from the cart. */
function WishlistPicks({
  picks,
  onAdd,
  adding,
  error,
}: {
  picks: WishlistItem[];
  onAdd: (courseId: string) => void;
  adding: string | null;
  error: unknown;
}) {
  return (
    <section aria-labelledby="from-wishlist" className="flex flex-col gap-3">
      <div className="flex items-baseline justify-between gap-3">
        <h2 id="from-wishlist" className="text-title">
          Trong danh sách yêu thích của bạn
        </h2>
        <Link href="/yeu-thich" className="shrink-0 text-body-sm font-semibold text-link">
          Xem cả danh sách
        </Link>
      </div>
      {error ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(error)}</AlertDescription>
        </Alert>
      ) : null}
      <ul className="grid gap-3 sm:grid-cols-2">
        {picks.map(({ course }) => (
          <li key={course.id} className="flex items-center gap-3 rounded-lg border bg-card p-3">
            <Link href={`/khoa-hoc/${course.slug}`} className="hidden shrink-0 sm:block" aria-hidden tabIndex={-1}>
              <CourseCover thumbnailUrl={course.thumbnail_url} colorKey={course.id} size="xs" className="w-24 rounded-sm" />
            </Link>
            <div className="min-w-0 flex-1">
              <Link
                href={`/khoa-hoc/${course.slug}`}
                className="line-clamp-1 text-body-sm font-semibold text-foreground hover:underline"
              >
                {course.title}
              </Link>
              <p className="text-body-sm font-semibold tabular-nums">{formatPrice(course.price)}</p>
            </div>
            <Button
              variant="outline"
              onClick={() => onAdd(course.id)}
              disabled={adding === course.id}
              aria-label={`Thêm ${course.title} vào giỏ`}
            >
              {adding === course.id ? <Loader2 className="animate-spin" aria-hidden /> : null}
              Thêm vào giỏ
            </Button>
          </li>
        ))}
      </ul>
    </section>
  );
}

/** An order that could not be taken to the gateway: why, and where it is now. */
function CheckoutError({ error, orderCode }: { error: unknown; orderCode: string | null }) {
  if (!error) return null;
  return (
    <Alert variant="destructive">
      <AlertTitle>{orderCode ? "Chưa mở được trang thanh toán" : "Chưa tạo được đơn hàng"}</AlertTitle>
      <AlertDescription>
        {apiErrorMessage(error)}
        {orderCode ? (
          <>
            {" "}
            Đơn <span className="font-semibold">{orderCode}</span> đã được tạo —{" "}
            <Link
              href={`/thanh-toan/ket-qua?ma=${encodeURIComponent(orderCode)}`}
              className="font-semibold underline underline-offset-4"
            >
              xem đơn
            </Link>
            .
          </>
        ) : null}
      </AlertDescription>
    </Alert>
  );
}

/**
 * The cart on its way: the headline, one line of the list, the "Xóa toàn bộ"
 * button and the summary card, where the real ones go.
 */
function CartSkeleton() {
  return (
    <SkeletonRegion label="Đang tải giỏ hàng…" className="space-y-6">
      <SkeletonText className="-mt-4 w-56" />
      <div className="grid items-start gap-8 lg:grid-cols-[minmax(0,1fr)_22.5rem]">
        <div className="space-y-4">
          <div className="flex gap-3 rounded-lg border p-4 sm:gap-4 sm:p-5">
            <Skeleton className="aspect-video w-24 shrink-0 sm:w-40" />
            <div className="min-w-0 flex-1 space-y-1">
              <SkeletonText size="title" className="w-3/4" />
              <SkeletonText size="body-sm" className="w-1/2" />
              <div className="flex gap-2 pt-2">
                <Skeleton className="h-8 w-28" />
                <Skeleton className="h-8 w-16" />
              </div>
            </div>
          </div>
          <div className="flex justify-end">
            <Skeleton className="h-8 w-40" />
          </div>
        </div>
        <div className="flex flex-col gap-5 rounded-lg border bg-card p-5 sm:p-6">
          <SkeletonText size="title" className="w-40" />
          <div className="space-y-2">
            <SkeletonText className="w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
          <Skeleton className="h-10 w-full" />
          <Skeleton className="hidden h-11 w-full lg:block" />
        </div>
      </div>
    </SkeletonRegion>
  );
}
