// node --test lib/courses/cover.test.ts  (npm test runs every *.test.ts)
//
// The stand-in course cover and the "what this course is made of" count on
// the course page. Both are pure functions the public pages lean on.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { COVER_GLYPHS, COVER_TINTS, coverFor } from "./cover.ts";
import { summarizeCurriculum } from "./curriculum-summary.ts";

const css = readFileSync(new URL("../../app/globals.css", import.meta.url), "utf8");

test("one course keeps one cover", () => {
  const id = "3c6e7eb3-6a9e-4c7c-ab5e-3a144714fa74";
  assert.deepEqual(coverFor(id), coverFor(id));
});

test("the covers of many courses use every tint and every glyph", () => {
  const tints = new Set<string>();
  const glyphs = new Set<string>();
  for (let i = 0; i < 400; i += 1) {
    const { tint, glyph } = coverFor(`course-${i}`);
    tints.add(tint.family);
    glyphs.add(glyph);
  }
  assert.equal(tints.size, COVER_TINTS.length);
  assert.equal(glyphs.size, COVER_GLYPHS.length);
});

test("every cover colour is a step the design system defines, never turmeric", () => {
  for (const tint of COVER_TINTS) {
    for (const cls of [tint.background, tint.strong, tint.soft, tint.ink, tint.glyph]) {
      const step = cls.replace(/^(bg|text)-/, "");
      assert.ok(!step.startsWith("turmeric"), `${cls}: turmeric is for rewards`);
      // A step missing from @theme would fall back to Tailwind's own colour.
      assert.match(css, new RegExp(`--color-${step}:\\s*#`), `${cls} is not in globals.css`);
    }
  }
});

test("the curriculum summary counts lessons by type, in page order, skipping absent types", () => {
  const lesson = (type: "video" | "article" | "quiz" | "code_exercise", i: number) => ({
    id: `${type}-${i}`,
    title: `${type} ${i}`,
    type,
    position: i,
    is_preview: false,
  });
  const summary = summarizeCurriculum({
    course_id: "c",
    sections: [
      { id: "s1", title: "Một", position: 0, lessons: [lesson("code_exercise", 0), lesson("video", 1)] },
      { id: "s2", title: "Hai", position: 1, lessons: [lesson("video", 0), lesson("video", 1)] },
      { id: "s3", title: "Trống", position: 2, lessons: [] },
    ],
  } as never);
  assert.equal(summary.sections, 3);
  assert.equal(summary.lessons, 4);
  assert.deepEqual(summary.byType, [
    { type: "video", count: 3 },
    { type: "code_exercise", count: 1 },
  ]);
});
