"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Heart, ShoppingCart } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { CourseCard } from "@/components/courses/course-card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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

  const query = useQuery({
    queryKey: ["wishlist", page],
    queryFn: () => listWishlist(accessToken as string, page),
    enabled: status === "authenticated" && accessToken !== null,
  });

  // The same cache entry the header badge fills, so this costs no request and
  // lets each card say whether its course is already in the cart -- the only
  // feedback "Thêm vào giỏ" gets, since the card itself stays put.
  const cart = useQuery({
    queryKey: ["cart"],
    queryFn: () => getCart(accessToken as string),
    enabled: status === "authenticated" && accessToken !== null,
  });

  const unsave = useMutation({
    mutationFn: (courseId: string) =>
      removeFromWishlist(accessToken as string, courseId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["wishlist"] });
      queryClient.invalidateQueries({ queryKey: ["wishlist-ids"] });
    },
  });

  const toCart = useMutation({
    mutationFn: (courseId: string) => addToCart(accessToken as string, courseId),
    onSuccess: (updated: Cart) => queryClient.setQueryData(["cart"], updated),
  });

  if (status === "loading") {
    return (
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {[0, 1, 2].map((row) => (
          <div key={row} className="h-72 animate-pulse rounded-lg border bg-muted/40" />
        ))}
      </div>
    );
  }

  if (status === "anonymous") {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Đăng nhập để xem danh sách yêu thích</CardTitle>
          <CardDescription>
            Danh sách này gắn với tài khoản nên bạn mở được trên mọi thiết bị.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button asChild>
            <Link href="/dang-nhap?next=/yeu-thich">Đăng nhập</Link>
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (query.isError) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{apiErrorMessage(query.error)}</AlertDescription>
      </Alert>
    );
  }

  if (!query.data) {
    return (
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {[0, 1, 2].map((row) => (
          <div key={row} className="h-72 animate-pulse rounded-lg border bg-muted/40" />
        ))}
      </div>
    );
  }

  if (query.data.items.length === 0) {
    return (
      <div className="rounded-lg border border-dashed p-12 text-center">
        <Heart className="mx-auto mb-3 size-8 text-muted-foreground" aria-hidden />
        <p className="font-medium">Chưa có khóa học nào được lưu</p>
        <p className="mt-1 text-sm text-muted-foreground">
          Bấm “Lưu vào yêu thích” ở trang khóa học để dành lại xem sau.
        </p>
        <Button className="mt-4" asChild>
          <Link href="/khoa-hoc">Tìm khóa học</Link>
        </Button>
      </div>
    );
  }

  const pageCount = Math.max(1, Math.ceil(query.data.total / query.data.page_size));

  return (
    <div className="space-y-6">
      {toCart.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(toCart.error)}</AlertDescription>
        </Alert>
      ) : null}

      <p className="text-muted-foreground">{query.data.total} khóa học</p>

      <ul className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {query.data.items.map((item) => {
          const inCart = cart.data?.items.some(
            (line) => line.course.id === item.course.id,
          );

          return (
            <li key={item.course.id} className="flex h-full flex-col gap-2">
              <CourseCard course={item.course} />
              <div className="flex items-center justify-between gap-3 px-1">
                <p className="text-xs text-muted-foreground">
                  Lưu {formatDate(item.added_at)}
                </p>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => unsave.mutate(item.course.id)}
                    disabled={unsave.isPending}
                    aria-label={`Bỏ ${item.course.title} khỏi yêu thích`}
                  >
                    Bỏ lưu
                  </Button>
                  {inCart ? (
                    <Button size="sm" variant="outline" asChild>
                      <Link href="/gio-hang">
                        <ShoppingCart aria-hidden />
                        Đã ở trong giỏ
                      </Link>
                    </Button>
                  ) : (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => toCart.mutate(item.course.id)}
                      disabled={toCart.isPending}
                    >
                      <ShoppingCart aria-hidden />
                      Thêm vào giỏ
                    </Button>
                  )}
                </div>
              </div>
            </li>
          );
        })}
      </ul>

      {pageCount > 1 ? (
        <div className="flex items-center justify-center gap-3">
          <Button
            variant="outline"
            size="sm"
            disabled={page === 1}
            onClick={() => setPage((current) => current - 1)}
          >
            Trang trước
          </Button>
          <span className="text-sm text-muted-foreground">
            Trang {page} / {pageCount}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= pageCount}
            onClick={() => setPage((current) => current + 1)}
          >
            Trang sau
          </Button>
        </div>
      ) : null}
    </div>
  );
}
