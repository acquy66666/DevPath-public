// node --test lib/markdown/editing.test.ts  (npm test runs every *.test.ts)
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  applyReplacement,
  BULLETS,
  codeBlock,
  HEADING,
  imageMarkdown,
  insertBlock,
  link,
  NUMBERS,
  prefixLines,
  QUOTE,
  replaceOnce,
  table,
  TABLE_TEMPLATE,
  wrapInline,
  type Replacement,
} from "./editing.ts";

/** The text after the replacement, with the new selection shown as [ ]. */
function show(text: string, replacement: Replacement): string {
  const after = applyReplacement(text, replacement);
  const { start, end } = replacement.select;
  return `${after.slice(0, start)}[${after.slice(start, end)}]${after.slice(end)}`;
}

test("bold wraps the selection and keeps it selected", () => {
  assert.equal(show("một hai ba", wrapInline("một hai ba", { start: 4, end: 7 }, "**", "x")), "một **[hai]** ba");
});

test("bold with nothing selected writes a placeholder to type over", () => {
  assert.equal(show("ab", wrapInline("ab", { start: 1, end: 1 }, "**", "chữ đậm")), "a**[chữ đậm]**b");
});

test("bold on bold text takes it off", () => {
  const text = "một **hai** ba";
  assert.equal(show(text, wrapInline(text, { start: 6, end: 9 }, "**", "x")), "một [hai] ba");
});

test("a list marks every selected line, and a second click unmarks them", () => {
  const text = "đầu\nmột\nhai\ncuối";
  const once = prefixLines(text, { start: 5, end: 10 }, BULLETS.prefix, BULLETS.pattern);
  assert.equal(applyReplacement(text, once), "đầu\n- một\n- hai\ncuối");

  const marked = applyReplacement(text, once);
  const twice = prefixLines(marked, once.select, BULLETS.prefix, BULLETS.pattern);
  assert.equal(applyReplacement(marked, twice), text);
});

test("a numbered list counts, and replaces bullets rather than stacking on them", () => {
  const all = (text: string) => ({ start: 0, end: text.length });
  const number = (text: string) =>
    applyReplacement(
      text,
      prefixLines(text, all(text), NUMBERS.prefix, NUMBERS.pattern, NUMBERS.replaces),
    );
  assert.equal(number("một\nhai"), "1. một\n2. hai");
  assert.equal(number("- một\n- hai"), "1. một\n2. hai");
});

test("a heading replaces another heading level instead of adding to it", () => {
  const text = "### Tiêu đề";
  const result = prefixLines(text, { start: 2, end: 2 }, HEADING.prefix, HEADING.pattern);
  assert.equal(applyReplacement(text, result), "Tiêu đề");
  const plain = "Tiêu đề";
  assert.equal(
    applyReplacement(plain, prefixLines(plain, { start: 0, end: 0 }, HEADING.prefix, HEADING.pattern)),
    "## Tiêu đề",
  );
});

test("a selection ending just after a newline leaves the next line alone", () => {
  const text = "một\nhai\n";
  const result = prefixLines(text, { start: 0, end: 4 }, QUOTE.prefix, QUOTE.pattern);
  assert.equal(applyReplacement(text, result), "> một\nhai\n");
});

test("a block gets a blank line on each side, and no more than one", () => {
  assert.equal(applyReplacement("trước", insertBlock("trước", { start: 5, end: 5 }, "B")), "trước\n\nB");
  assert.equal(applyReplacement("a\n\nb", insertBlock("a\n\nb", { start: 3, end: 3 }, "B")), "a\n\nB\n\nb");
  assert.equal(applyReplacement("", insertBlock("", { start: 0, end: 0 }, "B")), "B");
  assert.equal(applyReplacement("a\nb", insertBlock("a\nb", { start: 2, end: 2 }, "B")), "a\n\nB\n\nb");
});

test("a table is a valid GFM table with the first header selected", () => {
  const result = table("", { start: 0, end: 0 });
  assert.equal(applyReplacement("", result), TABLE_TEMPLATE);
  assert.equal(show("", result).split("\n")[0], "| [Cột 1] | Cột 2 |");
});

test("a code block wraps the selection and selects the language", () => {
  const text = "x = 1";
  assert.equal(show(text, codeBlock(text, { start: 0, end: 5 })), "```[python]\nx = 1\n```");
});

test("a link keeps the selected words and selects the address to fill in", () => {
  const text = "xem tài liệu";
  assert.equal(show(text, link(text, { start: 4, end: 12 })), "xem [tài liệu]([https://])");
});

test("a picture's description cannot close its own brackets", () => {
  assert.equal(imageMarkdown("a]b[c", "https://x/a.png"), "![abc](https://x/a.png)");
});

test("replacing a placeholder touches only the first match, and nothing once it is gone", () => {
  assert.equal(replaceOnce("a X b X", "X", "Y"), "a Y b X");
  assert.equal(replaceOnce("a b", "X", "Y"), "a b");
});
