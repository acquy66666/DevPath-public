// node --test lib/instructor/teaching-view.test.ts  (npm test runs every *.test.ts)
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  curriculumCounts,
  filterCourses,
  greetingLine,
  pendingTasks,
  reviewChecklist,
  sectionSummary,
  statusCounts,
  visibleFilters,
} from "./teaching-view.ts";

type Status = "draft" | "pending_review" | "published" | "rejected";
const course = (id: string, status: Status) => ({ id, title: `Khóa ${id}`, status });
const lesson = (type: "video" | "article" | "code_exercise" | "quiz", is_preview = false) => ({
  id: Math.random().toString(36),
  title: "x",
  type,
  position: 0,
  is_preview,
});

test("status chips show only the statuses that have courses", () => {
  const list = [course("a", "published"), course("b", "published"), course("c", "draft")];
  assert.deepEqual(statusCounts(list), { all: 3, published: 2, pending_review: 0, draft: 1, rejected: 0 });
  assert.deepEqual(
    visibleFilters(list).map((f) => `${f.label} · ${f.count}`),
    ["Tất cả · 3", "Đã xuất bản · 2", "Bản nháp · 1"],
  );
  assert.deepEqual(filterCourses(list, "draft").map((c) => c.id), ["c"]);
  assert.equal(filterCourses(list, "all").length, 3);
});

test("waiting tasks: questions first, then rejected, then drafts; pending review is not the instructor's move", () => {
  const list = [course("d", "draft"), course("p", "pending_review"), course("r", "rejected")];
  const tasks = pendingTasks(list, 3);
  assert.deepEqual(tasks.map((t) => t.kind), ["questions", "rejected", "draft"]);
  assert.equal(tasks[1].href, "/giang-day/r?tab=thong-tin");
  assert.equal(tasks[2].href, "/giang-day/d");
  assert.deepEqual(pendingTasks([course("p", "published")], 0), []);
});

test("the greeting line counts, and says when nothing is waiting", () => {
  assert.equal(greetingLine(7, 57, 3), "7 khóa học, 57 học viên. Có 3 việc đang chờ bạn.");
  assert.equal(greetingLine(2, 0, 0), "2 khóa học, 0 học viên. Không có việc nào đang chờ bạn.");
  assert.match(greetingLine(0, 0, 0), /khóa học đầu tiên/);
});

test("a chapter's summary names each lesson type it holds, in a fixed order", () => {
  assert.equal(
    sectionSummary({ lessons: [lesson("quiz"), lesson("video"), lesson("code_exercise"), lesson("video")] }),
    "4 bài · 2 video · 1 bài tập code · 1 trắc nghiệm",
  );
  assert.equal(sectionSummary({ lessons: [] }), "Chưa có bài nào");
});

test("curriculum counts add up every chapter", () => {
  const counts = curriculumCounts([
    { lessons: [lesson("video", true), lesson("article")] },
    { lessons: [lesson("quiz")] },
  ]);
  assert.deepEqual(counts, { sections: 2, video: 1, article: 1, code_exercise: 0, quiz: 1, preview: 1 });
});

test("the review checklist: blank text is missing, an empty chapter fails, a preview lesson counts", () => {
  const checks = reviewChecklist({ subtitle: "  ", description: "Có" }, [
    { lessons: [lesson("video", true)] },
    { lessons: [] },
  ]);
  assert.deepEqual(
    checks.map((c) => c.done),
    [false, true, false, true],
  );
  // No curriculum yet (still loading or empty): nothing about chapters is done.
  assert.deepEqual(
    reviewChecklist({ subtitle: "a", description: "b" }, undefined).map((c) => c.done),
    [true, true, false, false],
  );
});
