/**
 * Why a recommendation card is there, in words: the line on top of the card
 * and the small tags naming which half of the hybrid recommender put it in
 * the block (`services/hybrid.py`). Learners see the reason; the committee
 * sees the model's two halves at work.
 *
 * `because` is the course in the reader's history that contributed most to
 * the card -- whichever half scored it. A card from the popular fallback has
 * no `because` and is labelled as such, never as if the model knew the reader.
 *
 * Type imports only: `npm test` runs this file under plain Node, which does
 * not resolve the app's extensionless imports.
 */

import type { RecommendedCourse } from "@/lib/api/recommendations";

export type ReasonTag = "learners" | "content" | "popular";

export const TAG_LABELS: Record<ReasonTag, string> = {
  learners: "Học viên giống bạn",
  content: "Nội dung gần",
  popular: "Phổ biến",
};

export type Reason = {
  /** Which picture leads the line. */
  icon: "both" | ReasonTag;
  /** Null when the course that earned the card was withdrawn since. */
  text: string | null;
  tags: ReasonTag[];
};

export function recommendationReason(item: Pick<RecommendedCourse, "because" | "sources">): Reason {
  const learners = item.sources.includes("collaborative");
  const content = item.sources.includes("content");
  if (!learners && !content) {
    return { icon: "popular", text: "Được nhiều học viên chọn", tags: ["popular"] };
  }

  const tags: ReasonTag[] = [];
  if (learners) tags.push("learners");
  if (content) tags.push("content");
  const title = item.because?.title ?? null;

  if (learners && content) {
    return { icon: "both", text: title ? `Vì bạn đã học ${title}` : null, tags };
  }
  if (learners) {
    return { icon: "learners", text: title ? `Người học ${title} cũng học khóa này` : null, tags };
  }
  return { icon: "content", text: title ? `Gần nội dung với ${title}` : null, tags };
}
