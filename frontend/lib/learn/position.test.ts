// node --test lib/learn/position.test.ts  (npm test runs every *.test.ts)
//
// The learning page's sense of place: "Chương 3 · Bài 2/6", the lessons
// before and after, each section's progress, which sections the contents
// opens on, reading time and "Tiếp tục từ …". All read from the table of
// contents already on the page.
import assert from "node:assert/strict";
import { test } from "node:test";

import type { Curriculum } from "../api/curriculum.ts";
import { locateLesson, openSectionsFor, readingMinutes, resumeAt, sectionProgress } from "./position.ts";

function lesson(id: string, type: "video" | "article" | "quiz" | "code_exercise" = "video") {
  return { id, title: `Bài ${id}`, type, position: 0, is_preview: false };
}

const COURSE: Curriculum = {
  sections: [
    { id: "s1", course_id: "c", title: "Bắt đầu với Python", position: 0, lessons: [lesson("a"), lesson("b"), lesson("c", "article")] },
    { id: "s2", course_id: "c", title: "Rẽ nhánh và vòng lặp", position: 1, lessons: [lesson("d"), lesson("e"), lesson("f", "quiz")] },
    { id: "s3", course_id: "c", title: "Chương trống", position: 2, lessons: [] },
  ],
};

test("a lesson knows its section, its number and its neighbours", () => {
  const place = locateLesson(COURSE, "e");
  assert.ok(place);
  assert.equal(place.sectionNumber, 2);
  assert.equal(place.sectionTitle, "Rẽ nhánh và vòng lặp");
  assert.equal(place.lessonNumber, 2);
  assert.equal(place.sectionLessonCount, 3);
  assert.equal(place.previous?.id, "d");
  assert.equal(place.next?.id, "f");
});

test("neighbours cross section borders, and the ends have none", () => {
  assert.equal(locateLesson(COURSE, "c")?.next?.id, "d");
  assert.equal(locateLesson(COURSE, "d")?.previous?.id, "c");
  assert.equal(locateLesson(COURSE, "a")?.previous, null);
  assert.equal(locateLesson(COURSE, "f")?.next, null);
});

test("a lesson that is not in the course has no place", () => {
  assert.equal(locateLesson(COURSE, "gone"), null);
  assert.equal(locateLesson(COURSE, null), null);
});

test("each section counts its own finished lessons", () => {
  const progress = sectionProgress(COURSE, new Set(["a", "b", "c", "e"]));
  assert.deepEqual(progress.get("s1"), { done: 3, total: 3 });
  assert.deepEqual(progress.get("s2"), { done: 1, total: 3 });
  assert.deepEqual(progress.get("s3"), { done: 0, total: 0 });
});

test("the contents opens on the section of the lesson on screen", () => {
  assert.deepEqual([...openSectionsFor(COURSE, "e")], ["s2"]);
  assert.deepEqual([...openSectionsFor(COURSE, null)], ["s1"]);
  assert.deepEqual([...openSectionsFor({ sections: [] }, null)], []);
});

test("reading time: the article of the demo course is a minute, markup is not words", () => {
  // "Ép kiểu và những cái bẫy quen thuộc", the seed article (582 characters).
  const article =
    "`input()` luôn trả về chuỗi. Đây là nguồn gốc của lỗi kinh điển nhất khi mới học: " +
    "`input(\"Tuổi: \") + 1` không cộng được, vì bạn đang cộng một chuỗi với một số.\n\n" +
    "`int(\"12\")` cho ra 12, nhưng `int(\"12.5\")` thì lỗi — phải qua `float` trước.";
  assert.equal(readingMinutes(article), 1);
  assert.equal(readingMinutes(""), 1);
  assert.equal(readingMinutes("# \n\n```python\n```\n**"), 1);
  assert.equal(readingMinutes(Array.from({ length: 1000 }, () => "chữ").join(" ")), 4);
});

test("Tiếp tục từ: only a real place to come back to", () => {
  assert.equal(resumeAt(140, 498, false), 140);
  assert.equal(resumeAt(140, 498, true), null, "a finished lesson starts again");
  assert.equal(resumeAt(4, 498, false), null, "a few seconds in is not a place");
  assert.equal(resumeAt(0, 498, false), null);
  assert.equal(resumeAt(undefined, 498, false), null);
  assert.equal(resumeAt(497.5, 498, false), null, "the very end is the end");
  assert.equal(resumeAt(140, null, false), 140, "the length may still be unknown");
});
