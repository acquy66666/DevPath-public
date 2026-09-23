"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Heart, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  addToWishlist,
  listWishlistedCourseIds,
  removeFromWishlist,
} from "@/lib/api/commerce";
import { useAuth } from "@/lib/auth/auth-provider";

/**
 * The heart on a course page: save it for later, or stop saving it.
 *
 * Asks for the ids of everything saved rather than about this one course. It
 * is one small response, it is shared with any other card on the page that
 * wants a heart, and it means the toggle knows its own state without an
 * endpoint that exists only to answer "is this one saved?".
 *
 * Nothing is drawn for a signed-out visitor: saving needs an account, and a
 * heart that answers "đăng nhập đi" is a worse invitation than the sign-in
 * button already on the page.
 */
export function WishlistButton({ courseId }: { courseId: string }) {
  const { accessToken, status } = useAuth();
  const queryClient = useQueryClient();
  const signedIn = status === "authenticated" && accessToken !== null;

  const saved = useQuery({
    queryKey: ["wishlist-ids"],
    queryFn: () => listWishlistedCourseIds(accessToken as string),
    enabled: signedIn,
  });

  const isSaved = saved.data?.includes(courseId) ?? false;

  const toggle = useMutation({
    mutationFn: () =>
      isSaved
        ? removeFromWishlist(accessToken as string, courseId)
        : addToWishlist(accessToken as string, courseId),
    onSuccess: () => {
      // Both queries change: the ids drive this heart, the list drives the
      // "Yêu thích" page the person may have open in another tab.
      queryClient.invalidateQueries({ queryKey: ["wishlist-ids"] });
      queryClient.invalidateQueries({ queryKey: ["wishlist"] });
    },
  });

  if (!signedIn) return null;

  return (
    <Button
      variant="outline"
      className="w-full"
      onClick={() => toggle.mutate()}
      disabled={toggle.isPending || saved.isLoading}
      aria-pressed={isSaved}
    >
      {toggle.isPending ? (
        <Loader2 className="animate-spin" aria-hidden />
      ) : (
        <Heart
          className={isSaved ? "fill-current text-red-500" : undefined}
          aria-hidden
        />
      )}
      {isSaved ? "Bỏ khỏi yêu thích" : "Lưu vào yêu thích"}
    </Button>
  );
}
