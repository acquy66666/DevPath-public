// node --test lib/recommendations/reason.test.ts  (npm test runs every *.test.ts)
//
// The line and tags on a "Gợi ý cho bạn" card: which half of the hybrid put
// it there, said plainly, and a popular fallback never dressed up as personal.
import assert from "node:assert/strict";
import { test } from "node:test";

import type { RecommendationReason, RecommendationSource } from "../api/recommendations.ts";
import { TAG_LABELS, recommendationReason } from "./reason.ts";

const DSA: RecommendationReason = {
  id: "1fcef1d9-cf34-4ecf-89c1-e98af369aac9",
  title: "Cấu trúc dữ liệu & giải thuật với Python",
  slug: "cau-truc-du-lieu-va-giai-thuat-voi-python",
};

function card(sources: RecommendationSource[], because: RecommendationReason | null = DSA) {
  return { sources, because };
}

test("both halves: the course that earned it, and both tags", () => {
  assert.deepEqual(recommendationReason(card(["collaborative", "content"])), {
    icon: "both",
    text: "Vì bạn đã học Cấu trúc dữ liệu & giải thuật với Python",
    tags: ["learners", "content"],
  });
});

test("one half: a sentence that says which", () => {
  assert.deepEqual(recommendationReason(card(["collaborative"])), {
    icon: "learners",
    text: "Người học Cấu trúc dữ liệu & giải thuật với Python cũng học khóa này",
    tags: ["learners"],
  });
  assert.deepEqual(recommendationReason(card(["content"])), {
    icon: "content",
    text: "Gần nội dung với Cấu trúc dữ liệu & giải thuật với Python",
    tags: ["content"],
  });
});

test("the popular fallback says it is popular, not personal", () => {
  assert.deepEqual(recommendationReason(card(["popular"], null)), {
    icon: "popular",
    text: "Được nhiều học viên chọn",
    tags: ["popular"],
  });
});

test("a withdrawn reason leaves the tags and drops the sentence", () => {
  assert.deepEqual(recommendationReason(card(["collaborative", "content"], null)), {
    icon: "both",
    text: null,
    tags: ["learners", "content"],
  });
});

test("tag labels", () => {
  assert.deepEqual(TAG_LABELS, { learners: "Học viên giống bạn", content: "Nội dung gần", popular: "Phổ biến" });
});
