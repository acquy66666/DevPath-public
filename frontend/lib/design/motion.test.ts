// node --test lib/design/motion.test.ts  (npm test runs every *.test.ts)
//
// The motion rules of the design system (docs/ui-ux/design-system/project/
// components/Motion): timings come from the tokens, only transform and
// opacity move, and nothing moves for a reader who asked for reduced motion.
// These checks read the source, so a new screen that slides without asking
// fails here instead of in front of someone it makes dizzy.
import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../../", import.meta.url));

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? walk(path) : [path];
  });
}

// Naomi's drawings and choreography are checked by lib/mascot; the dev
// preview pages are not part of the site.
const files = [...walk(join(root, "app")), ...walk(join(root, "components"))].filter(
  (f) =>
    f.endsWith(".tsx") &&
    !f.includes(`${sep}mascot${sep}art${sep}`) &&
    !f.includes(`${sep}(dev)${sep}`),
);
const name = (f: string) => relative(root, f).split(sep).join("/");
/** The code without its comments, which may well name what the code must not use. */
const code = (f: string) =>
  readFileSync(f, "utf8").replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/.*$/gm, "$1");
/** Every string literal in the file: where class names live. */
const strings = (source: string) => source.match(/"[^"\n]*"|`[^`]*`|'[^'\n]*'/g) ?? [];

test("timings come from the motion tokens", () => {
  const raw = /\b(?:duration-\d+|duration-\[|ease-(?:linear|in|out|in-out)\b|ease-\[|delay-\d+)/;
  const found = files.flatMap((f) =>
    strings(code(f))
      .filter((s) => raw.test(s))
      .map((s) => `${name(f)}: ${s.match(raw)?.[0]}`),
  );
  assert.deepEqual(found, [], "use duration-{instant,fast,base,slow,progress} and ease-{standard,enter,exit,overshoot}");
});

test("only transform and opacity move", () => {
  const layout = /transition-\[[^\]]*\b(?:width|height|top|left|right|bottom|margin|padding)\b[^\]]*\]/;
  const found = files.flatMap((f) =>
    strings(code(f))
      .filter((s) => layout.test(s))
      .map((s) => `${name(f)}: ${s.match(layout)?.[0]}`),
  );
  assert.deepEqual(found, []);
});

test("every transform transition and looping animation asks about reduced motion", () => {
  // A transition that may move something, or an animation that keeps going.
  const moves =
    /(?:^|[\s"`'])(?:[\w-]+:)*(?:transition-transform|transition-\[[^\]]*\b(?:transform|translate|scale|rotate)\b[^\]]*\]|animate-(?:pulse|bounce|ping))\b/;
  const asks = /motion-(?:safe|reduce):/;
  const found = files.flatMap((f) =>
    strings(code(f))
      .filter((s) => moves.test(s) && !asks.test(s))
      .map((s) => `${name(f)}: ${s.trim().slice(0, 120)}`),
  );
  assert.deepEqual(found, [], "add motion-reduce:transition-none, or put the movement behind motion-safe:");
});

// `motion-reduce:after:transition-none` loses to
// `group-data-[variant=line]/tabs-list:after:transition-transform`: the group
// selector is more specific, so the bar went on sliding (measured in Chrome,
// motion/check.cjs). The off switch must carry the same variants.
test("a transition behind variants is switched off behind the same variants", () => {
  const variantMove = /(?:^|\s)((?:[\w\-[\]=/]+:)+)transition-(?:transform|\[[^\]]*\b(?:transform|translate|scale|rotate)\b[^\]]*\])/g;
  const found = files.flatMap((f) =>
    strings(code(f)).flatMap((s) =>
      [...s.matchAll(variantMove)]
        .map((m) => m[1])
        .filter((prefix) => !prefix.startsWith("motion-safe:") && !s.includes(`motion-reduce:${prefix}transition-none`))
        .map((prefix) => `${name(f)}: ${prefix}transition-* has no motion-reduce:${prefix}transition-none`),
    ),
  );
  assert.deepEqual(found, []);
});

test("a slide or zoom on enter and exit sits behind motion-safe", () => {
  const travel = /(?:^|\s)((?:[\w\-[\]=/]+:)*(?:slide-(?:in|out)-[\w-]+|zoom-(?:in|out)-[\w-]+))/g;
  const found = files.flatMap((f) =>
    strings(code(f)).flatMap((s) =>
      [...s.matchAll(travel)]
        .map((m) => m[1])
        .filter((cls) => !cls.startsWith("motion-safe:"))
        .map((cls) => `${name(f)}: ${cls}`),
    ),
  );
  assert.deepEqual(found, []);
});

test("globals.css stops every CSS animation for reduced motion", () => {
  const css = readFileSync(join(root, "app", "globals.css"), "utf8");
  const block = css.match(/@media \(prefers-reduced-motion: reduce\) \{([\s\S]*?)\n  \}/)?.[1] ?? "";
  assert.match(block, /animation-duration:\s*1ms !important/);
  assert.match(block, /animation-iteration-count:\s*1 !important/);
  assert.match(block, /scroll-behavior:\s*auto !important/);
});

test("progress bars glide on transform, not width", () => {
  const progress = code(join(root, "components", "ui", "progress.tsx"));
  assert.match(progress, /translateX/);
  assert.match(progress, /duration-progress/);
  assert.match(progress, /motion-reduce:transition-none/);
  const handRolled = files.filter(
    (f) => !f.endsWith(`${sep}progress.tsx`) && /role="progressbar"[\s\S]{0,400}style=\{\{\s*width/.test(code(f)),
  );
  assert.deepEqual(handRolled.map(name), [], "use <Progress> from components/ui/progress");
});
