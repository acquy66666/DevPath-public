"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Loader2, ShoppingCart } from "lucide-react";
import Link from "next/link";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { addToCart, getCart, type Cart } from "@/lib/api/commerce";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { useAuth } from "@/lib/auth/auth-provider";

/**
 * "Thêm vào giỏ hàng" on a paid course page.
 *
 * It reads the whole cart rather than asking about this one course: the cart
 * is bounded and the header is fetching it anyway, so the two share a cache
 * entry and the second component costs nothing. Adding writes the response
 * back into that entry, which is what makes the header badge move on the same
 * click without a refetch.
 */
export function AddToCartButton({ courseId }: { courseId: string }) {
  const { accessToken, status } = useAuth();
  const queryClient = useQueryClient();

  const cart = useQuery({
    queryKey: ["cart"],
    queryFn: () => getCart(accessToken as string),
    enabled: status === "authenticated" && accessToken !== null,
  });

  const add = useMutation({
    mutationFn: () => addToCart(accessToken as string, courseId),
    onSuccess: (updated: Cart) => {
      queryClient.setQueryData(["cart"], updated);
    },
  });

  const inCart = cart.data?.items.some((item) => item.course.id === courseId);

  if (inCart) {
    return (
      <div className="space-y-2">
        <Button className="w-full" asChild>
          <Link href="/gio-hang">Xem giỏ hàng</Link>
        </Button>
        <p className="flex items-center justify-center gap-2 text-xs text-muted-foreground">
          <Check className="size-3.5" aria-hidden />
          Khóa học đã ở trong giỏ hàng
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {add.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(add.error)}</AlertDescription>
        </Alert>
      ) : null}

      <Button
        className="w-full"
        onClick={() => add.mutate()}
        disabled={add.isPending || cart.isLoading}
      >
        {add.isPending ? (
          <>
            <Loader2 className="animate-spin" aria-hidden />
            Đang thêm…
          </>
        ) : (
          <>
            <ShoppingCart aria-hidden />
            Thêm vào giỏ hàng
          </>
        )}
      </Button>
    </div>
  );
}
