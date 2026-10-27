"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Heart, Loader2, ShoppingCart } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { useOwnedCourses } from "@/components/commerce/use-owned-courses";
import { CourseCard, CourseListSkeleton } from "@/components/courses/course-card";
import { Mascot } from "@/components/mascot/mascot";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Pager } from "@/components/ui/pager";
import {
  addToCart,
  getCart,
  listWishlist,
  removeFromWishlist,
  type Cart,
} from "@/lib/api/commerce";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { useAuth } from "@/lib/auth/auth-provider";
import { formatDate } from "@/lib/format";

/**
 * "Danh sách yêu thích" — the courses somebody saved for later.
 *
 * Paged, unlike the cart: nothing bounds how many courses a person saves, and
 * there is no total to compute that would need every row at once.
 */
export function WishlistView() {
  const { accessToken, status } = useAuth();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const signedIn = status === "authenticated" && accessToken !== null;

  const query = useQuery({
    queryKey: ["wishlist", page],
    queryFn: () => listWishlist(accessToken as string, page),
    enabled: signedIn,
  });

  // The same cache entry the header badge fills, so this costs no request and
  // lets each card say whether its course is already in the cart.
  const cart = useQuery({
    queryKey: ["cart"],
    queryFn: () => getCart(accessToken as string),
    enabled: signedIn,
  });

  const ownership = useOwnedCourses(
    signedIn ? accessToken : null,
    query.data?.items.map((item) => item.course.id) ?? [],
  );

  const unsave = useMutation({
    mutationFn: (courseId: string) => removeFromWishlist(accessToken as string, courseId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["wishlist"] });
      queryClient.invalidateQueries({ queryKey: ["wishlist-ids"] });
    },
  });

  const toCart = useMutation({
    mutationFn: (courseId: string) => addToCart(accessToken as string, courseId),
    onSuccess: (updated: Cart) => queryClient.setQueryData(["cart"], updated),
  });

  if (status === "loading") return <CourseListSkeleton label="Đang tải danh sách yêu thích…" />;

  if (status === "anonymous") {
    return (
      <div className="@container rounded-lg border bg-card">
        <div className="flex flex-col items-center gap-4 px-6 py-10 text-center @md:flex-row @md:justify-center @md:gap-8 @md:px-10 @md:text-left">
          <Mascot mood="empty-courses" size="md" />
          <div className="flex min-w-0 flex-col items-center gap-1 @md:items-start">
            <h2 className="text-title text-foreground">Đăng nhập để xem danh sách yêu thích</h2>
            <p className="max-w-md text-body-sm text-muted-foreground">
              Danh sách này gắn với tài khoản nên bạn mở được trên mọi thiết bị.
            </p>
            <div className="mt-3">
              <Button asChild>
                <Link href="/dang-nhap?next=/yeu-thich">Đăng nhập</Link>
              </Button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (query.isError) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{apiErrorMessage(query.error)}</AlertDescription>
      </Alert>
    );
  }

  if (!query.data) return <CourseListSkeleton label="Đang tải danh sách yêu thích…" />;

  if (query.data.items.length === 0) {
    return (
      <EmptyState
        mood="empty-courses"
        title="Chưa có khóa học nào được lưu"
        description="Bấm “Lưu vào yêu thích” ở trang khóa học để dành lại xem sau."
        action={
          <Button asChild>
            <Link href="/khoa-hoc">Tìm khóa học</Link>
          </Button>
        }
      />
    );
  }

  const cartIds = new Set(cart.data?.items.map((line) => line.course.id) ?? []);
  const inCartHere = query.data.items.filter((item) => cartIds.has(item.course.id)).length;

  return (
    <div className="space-y-6">
      <div className="-mt-4 flex flex-wrap items-end justify-between gap-3">
        <p className="text-body text-muted-foreground">
          {query.data.total} khóa học bạn để dành
          {inCartHere > 0 ? ` · ${inCartHere} khóa đã ở trong giỏ` : ""}
        </p>
        {cart.data && cart.data.items.length > 0 ? (
          <Button variant="outline" asChild>
            <Link href="/gio-hang">
              <ShoppingCart aria-hidden />
              Xem giỏ hàng
            </Link>
          </Button>
        ) : null}
      </div>

      {toCart.isError || unsave.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(toCart.isError ? toCart.error : unsave.error)}</AlertDescription>
        </Alert>
      ) : null}

      <ul className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {query.data.items.map((item) => {
          const { course } = item;
          const inCart = cartIds.has(course.id);
          const free = Number(course.price) === 0;
          const owned = ownership.owned.has(course.id);
          const adding = toCart.isPending && toCart.variables === course.id;
          const removing = unsave.isPending && unsave.variables === course.id;

          return (
            <li key={course.id} className="relative flex h-full flex-col gap-3">
              <CourseCard course={course} />

              {/* Over the cover, beside the card's link rather than inside it. */}
              <Button
                variant="outline"
                size="icon-lg"
                className="absolute top-3 right-3 rounded-full border-transparent text-destructive shadow-sm"
                onClick={() => unsave.mutate(course.id)}
                disabled={removing}
                aria-pressed
                aria-label={`Bỏ ${course.title} khỏi yêu thích`}
              >
                {removing ? <Loader2 className="animate-spin" aria-hidden /> : <Heart className="fill-current" aria-hidden />}
              </Button>

              <div className="flex items-center justify-between gap-3 px-1">
                <p className="text-caption font-normal text-muted-foreground">Lưu ngày {formatDate(item.added_at)}</p>
                {owned ? (
                  <Button variant="secondary" asChild>
                    <Link href={`/hoc/${course.slug}`} aria-label={`Đã có · Vào học ${course.title}`}>
                      <Check aria-hidden />
                      Đã có · Vào học
                    </Link>
                  </Button>
                ) : free ? (
                  <Button variant="secondary" asChild>
                    <Link href={`/khoa-hoc/${course.slug}`}>Học miễn phí</Link>
                  </Button>
                ) : inCart ? (
                  <Button variant="secondary" asChild>
                    <Link href="/gio-hang" aria-label={`${course.title}: đã ở trong giỏ`}>
                      <Check aria-hidden />
                      Đã ở trong giỏ
                    </Link>
                  </Button>
                ) : (
                  <Button onClick={() => toCart.mutate(course.id)} disabled={adding}>
                    {adding ? <Loader2 className="animate-spin" aria-hidden /> : <ShoppingCart aria-hidden />}
                    Thêm vào giỏ
                  </Button>
                )}
              </div>
            </li>
          );
        })}
      </ul>

      <Pager page={page} pageSize={query.data.page_size} total={query.data.total} onPage={setPage} />
    </div>
  );
}
