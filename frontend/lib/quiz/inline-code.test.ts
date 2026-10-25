// node --test lib/quiz/inline-code.test.ts  (npm test runs every *.test.ts)
//
// Quiz text is plain text with one piece of Markdown: `code` in backticks.
// The AI prompt asks for it and instructors type it, and before phase 7 the
// page printed the backticks as they were (phase-4/quiz-demo.txt §5).
import assert from "node:assert/strict";
import { test } from "node:test";

import { splitInlineCode } from "./inline-code.ts";

test("backticks become code, the rest stays text", () => {
  assert.deepEqual(splitInlineCode("đối số duy nhất là `range(5)`, các số"), [
    { code: false, text: "đối số duy nhất là " },
    { code: true, text: "range(5)" },
    { code: false, text: ", các số" },
  ]);
});

test("several spans, and one that is the whole text", () => {
  assert.deepEqual(splitInlineCode("`a` và `b`"), [
    { code: true, text: "a" },
    { code: false, text: " và " },
    { code: true, text: "b" },
  ]);
  assert.deepEqual(splitInlineCode("`range(1, 11)`"), [{ code: true, text: "range(1, 11)" }]);
});

test("text without a pair of backticks is left exactly as written", () => {
  assert.deepEqual(splitInlineCode("Bên ngoài vòng lặp"), [{ code: false, text: "Bên ngoài vòng lặp" }]);
  assert.deepEqual(splitInlineCode("dấu ` lẻ loi"), [{ code: false, text: "dấu ` lẻ loi" }]);
  assert.deepEqual(splitInlineCode("``"), [{ code: false, text: "``" }]);
  assert.deepEqual(splitInlineCode(""), []);
});

test("a span does not run across lines", () => {
  assert.deepEqual(splitInlineCode("`a\nb`"), [{ code: false, text: "`a\nb`" }]);
});
