"use client";

import { useQuery } from "@tanstack/react-query";
import { Sparkles, TrendingUp } from "lucide-react";

import { CourseCard } from "@/components/courses/course-card";
import {
  CourseBlock,
  CourseBlockSkeleton,
} from "@/components/recommendations/course-block";
import { apiErrorMessage } from "@/lib/api/error-messages";
import {
  getRecommendations,
  type RecommendedCourse,
  type Recommendations,
} from "@/lib/api/recommendations";
import { useAuth } from "@/lib/auth/auth-provider";

const TITLE = "Gợi ý cho bạn";
/** One row on a wide screen. */
const LIMIT = 4;

/**
 * "Gợi ý cho bạn" on the home page -- signed-in readers only.
 *
 * A Client Component because the answer is one person's history and needs
 * the access token, which only the browser holds. Nothing is drawn for a
 * signed-out visitor: there is no anonymous version of a recommendation, and
 * the catalogue one click away already is the "popular" list.
 */
export function RecommendedForYou() {
  const { accessToken, status } = useAuth();
  const signedIn = status === "authenticated" && accessToken !== null;

  const query = useQuery({
    queryKey: ["recommendations", LIMIT],
    queryFn: () => getRecommendations(accessToken as string, LIMIT),
    enabled: signedIn,
  });

  if (!signedIn) return null;

  if (query.isError) {
    return (
      <CourseBlock title={TITLE}>
        <p className="col-span-full text-sm text-muted-foreground">
          Chưa tải được gợi ý lúc này: {apiErrorMessage(query.error)}
        </p>
      </CourseBlock>
    );
  }

  if (!query.data) return <CourseBlockSkeleton title={TITLE} count={LIMIT} described />;
  if (query.data.items.length === 0) return null;

  return (
    <CourseBlock title={TITLE} description={describe(query.data)}>
      {query.data.items.map((item) => (
        <CourseCard key={item.id} course={item} note={reason(item)} />
      ))}
    </CourseBlock>
  );
}

/**
 * Where the row came from, said plainly. A block made only of popular
 * courses must not claim to know the reader: that is the fallback talking,
 * not the model.
 */
function describe(block: Recommendations): string {
  const personal = block.items.some((item) => !item.sources.includes("popular"));
  if (personal) {
    return "Dựa trên các khóa bạn đã học và lựa chọn của những học viên giống bạn.";
  }
  return block.generated_at === null
    ? "Bạn chưa có lịch sử học để gợi ý riêng — đây là những khóa được nhiều học viên chọn."
    : "Chưa có gợi ý mới từ lịch sử học của bạn — đây là những khóa được nhiều học viên chọn.";
}

function reason(item: RecommendedCourse) {
  if (item.because) {
    return (
      <>
        <Sparkles className="size-3.5 shrink-0" aria-hidden />
        <span className="line-clamp-1">Vì bạn đã học {item.because.title}</span>
      </>
    );
  }
  if (item.sources.includes("popular")) {
    return (
      <>
        <TrendingUp className="size-3.5 shrink-0" aria-hidden />
        Được nhiều học viên chọn
      </>
    );
  }
  // Recommended by the model, but the course that earned it has since been
  // withdrawn: the card stands, the sentence explaining it does not.
  return null;
}
