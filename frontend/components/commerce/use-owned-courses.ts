"use client";

import { useQueries } from "@tanstack/react-query";

import { getMyEnrollment } from "@/lib/api/enrollments";

/**
 * Which of these courses the reader is already enrolled in.
 *
 * The wishlist keeps a course after it is bought (the API does not take it
 * out), so the wishlist page and the cart's "from your wishlist" row must ask.
 * One small request per course, under the same `["enrollment", id]` key the
 * course page uses -- so a purchase, which invalidates `["enrollment"]`,
 * refreshes these too. Lists here are a page of a wishlist at most.
 */
export function useOwnedCourses(accessToken: string | null, courseIds: readonly string[]) {
  const results = useQueries({
    queries: courseIds.map((id) => ({
      queryKey: ["enrollment", id],
      queryFn: () => getMyEnrollment(accessToken as string, id),
      enabled: accessToken !== null,
    })),
  });
  const owned = new Set(courseIds.filter((_, index) => results[index]?.data));
  const settled = results.every((result) => !result.isPending);
  return { owned, settled };
}
