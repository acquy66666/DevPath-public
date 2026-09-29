"use client";

import { useQuery } from "@tanstack/react-query";
import { ShoppingCart } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { getCart } from "@/lib/api/commerce";
import { useAuth } from "@/lib/auth/auth-provider";

/**
 * The cart in the header: an icon, and how many courses are in it.
 *
 * Signed-out visitors get nothing at all rather than an empty cart icon —
 * there is no cart to open, and the header already has a "Đăng nhập" button
 * two elements to the right.
 *
 * The count is `items.length`, including lines the person turned out to
 * already own. Those still sit in the cart and still want dealing with; the
 * cart page is where they are explained, and a badge that quietly disagreed
 * with the list underneath would be the more confusing of the two.
 */
export function CartBadge() {
  const { accessToken, status } = useAuth();

  const cart = useQuery({
    queryKey: ["cart"],
    queryFn: () => getCart(accessToken as string),
    enabled: status === "authenticated" && accessToken !== null,
  });

  if (status !== "authenticated") return null;

  const count = cart.data?.items.length ?? 0;

  return (
    <Button
      variant="ghost"
      size="sm"
      className="relative h-10 px-2 sm:px-3"
      aria-label={count > 0 ? `Giỏ hàng, ${count} khóa học` : "Giỏ hàng"}
      asChild
    >
      <Link href="/gio-hang">
        <ShoppingCart className="size-5" aria-hidden />
        {count > 0 ? (
          <span
            className="absolute -top-0.5 right-0 flex size-5 items-center justify-center rounded-full bg-primary text-[0.7rem] font-medium text-primary-foreground"
            aria-hidden
          >
            {count}
          </span>
        ) : null}
      </Link>
    </Button>
  );
}
