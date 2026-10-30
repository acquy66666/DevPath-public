"use client";

import dynamic from "next/dynamic";

import { useAuth } from "@/lib/auth/auth-provider";

const RecommendedForYou = dynamic(
  () => import("@/components/recommendations/recommended-for-you").then((m) => m.RecommendedForYou),
  { ssr: false },
);

/**
 * "Gợi ý cho bạn" on the home page, fetched only for a signed-in reader: it
 * draws nothing for a visitor -- a recommendation is one person's history --
 * so a visitor's first load should not carry its code either. It appeared
 * after the session was restored before, and still does.
 */
export function HomeRecommendations() {
  const { status } = useAuth();
  return status === "authenticated" ? <RecommendedForYou /> : null;
}
