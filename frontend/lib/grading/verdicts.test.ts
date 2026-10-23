// node --test lib/grading/verdicts.test.ts  (npm test runs every *.test.ts)
//
// The seven letters are drawn from three tables (words, colours, Naomi). A
// letter missing from one of them, or a colour class naming a token that does
// not exist, would draw a blank -- these checks read globals.css and the mood
// list so that cannot happen quietly.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { MOODS } from "../mascot/moods.ts";
import {
  VERDICT_CLASSES,
  VERDICT_HINTS,
  VERDICT_LABELS,
  VERDICT_MOOD,
  VERDICTS,
  asVerdict,
  verdictLabel,
} from "./verdicts.ts";

const read = (path: string) => readFileSync(new URL(path, import.meta.url), "utf8");
const globals = read("../../app/globals.css");

test("every letter has words, a hint, a mood and three colours", () => {
  for (const verdict of VERDICTS) {
    assert.ok(VERDICT_LABELS[verdict], `${verdict} label`);
    assert.ok(VERDICT_HINTS[verdict], `${verdict} hint`);
    assert.ok((MOODS as readonly string[]).includes(VERDICT_MOOD[verdict]), `${verdict} mood`);
    const { text, soft, solid, border } = VERDICT_CLASSES[verdict];
    const slug = verdict.toLowerCase();
    assert.equal(text, `text-verdict-${slug}`);
    assert.equal(soft, `bg-verdict-${slug}-soft`);
    assert.equal(solid, `bg-verdict-${slug}-solid`);
    assert.equal(border, `border-verdict-${slug}-solid`);
    for (const token of [`verdict-${slug}`, `verdict-${slug}-soft`, `verdict-${slug}-solid`]) {
      assert.match(globals, new RegExp(`--color-${token}: var\\(--${token}\\);`), `${token} in @theme inline`);
    }
  }
});

test("Naomi's answers follow the reaction map", () => {
  assert.deepEqual(VERDICT_MOOD, {
    AC: "celebrate",
    WA: "partial",
    TLE: "sleepy",
    MLE: "stuffed",
    RE: "dizzy",
    CE: "tangled",
    SE: "sorry",
  });
});

test("a letter this page has never heard of is drawn as a system error", () => {
  assert.equal(asVerdict("AC"), "AC");
  assert.equal(asVerdict("XYZ"), "SE");
  assert.equal(asVerdict(null), null);
  assert.equal(verdictLabel(null), "Chưa chấm");
  assert.equal(verdictLabel("XYZ"), "XYZ");
});

test("the golden flow waits on the accepted hint, word for word", () => {
  const spec = read("../../e2e/golden-flow.spec.ts");
  assert.ok(spec.includes(VERDICT_HINTS.AC), "e2e/golden-flow.spec.ts no longer matches VERDICT_HINTS.AC");
});
