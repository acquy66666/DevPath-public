// node --test lib/design/tokens.test.ts  (npm test runs every *.test.ts)
//
// app/globals.css is the design system in code. These checks keep it equal to
// the artifact's tokens.json (docs/ui-ux/design-system/project), and keep
// components/ui reading the semantic layer only. A difference fails here; fix
// whichever side is wrong -- code wins, so usually palette.py.
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { test } from "node:test";

import { extendTailwindMerge } from "tailwind-merge";

import { DURATIONS, EASINGS, MERGE_CONFIG, TEXT_STYLES } from "./tokens.ts";

const read = (path: string) => readFileSync(new URL(path, import.meta.url), "utf8");
const tokens = JSON.parse(read("../../../docs/ui-ux/design-system/project/tokens.json"));
const globals = read("../../app/globals.css");

type Token = { name: string; value: string };
const colors: Token[] = tokens.color.tokens;
const isPaletteStep = (t: Token) => /^#/.test(t.value) && /^[a-z]+-\d+$/.test(t.name);
const palette = colors.filter(isPaletteStep);
const semantic = colors.filter((t) => !isPaletteStep(t));

/** The declarations of every block that opens with `opener` (no nested braces). */
function declarations(opener: RegExp): Map<string, string> {
  const out = new Map<string, string>();
  const blocks = new RegExp(`${opener.source}\\s*\\{([^}]*)\\}`, "g");
  for (const [, body] of globals.matchAll(blocks)) {
    const code = body.replace(/\/\*[\s\S]*?\*\//g, "");
    for (const [, name, value] of code.matchAll(/(--[a-z0-9-]+):\s*([^;]+);/g)) out.set(name, value.trim());
  }
  return out;
}

const themeStatic = declarations(/@theme static/);
const themeInline = declarations(/@theme inline/);
const theme = declarations(/@theme/);
const root = declarations(/:root/);

const px = (rem: string) => `${parseFloat(rem) * 16}px`;

test("the palette is tokens.json's, step for step", () => {
  const css = new Map([...themeStatic].filter(([name]) => /^--color-[a-z]+-\d+$/.test(name)));
  for (const t of palette) assert.equal(css.get(`--color-${t.name}`), t.value, `--color-${t.name}`);
  assert.deepEqual(
    [...css.keys()].sort(),
    palette.map((t) => `--color-${t.name}`).sort(),
    "globals.css has a palette step tokens.json does not",
  );
});

test("every semantic token is a variable in :root and a utility colour", () => {
  for (const t of semantic) {
    const ref = /^\{(.+)\}$/.exec(t.value);
    assert.equal(root.get(`--${t.name}`), ref ? `var(--color-${ref[1]})` : t.value, `:root --${t.name}`);
    assert.equal(themeInline.get(`--color-${t.name}`), `var(--${t.name})`, `@theme inline --color-${t.name}`);
  }
  const names = new Set(semantic.map((t) => t.name));
  for (const name of root.keys()) assert.ok(names.has(name.slice(2)), `:root ${name} is not in tokens.json`);
});

test("type scale, radius, shadow and motion are tokens.json's", () => {
  const styles = tokens.type.groups.flatMap((g: { styles: unknown[] }) => g.styles) as {
    name: string;
    fontSize: string;
    lineHeight: string;
    fontWeight: number;
    letterSpacing?: string;
  }[];
  for (const s of styles) {
    assert.equal(px(theme.get(`--text-${s.name}`) ?? "NaN"), s.fontSize, `--text-${s.name}`);
    assert.equal(px(theme.get(`--text-${s.name}--line-height`) ?? "NaN"), s.lineHeight, `${s.name} line height`);
    assert.equal(theme.get(`--text-${s.name}--font-weight`), String(s.fontWeight), `${s.name} weight`);
    assert.equal(theme.get(`--text-${s.name}--letter-spacing`), s.letterSpacing, `${s.name} letter spacing`);
  }
  assert.deepEqual([...TEXT_STYLES], styles.map((s) => s.name), "lib/design/tokens.ts TEXT_STYLES");

  for (const r of tokens.radius.tokens as Token[]) {
    if (r.name === "radius-full") continue; // Tailwind's rounded-full
    assert.equal(px(theme.get(`--${r.name}`) ?? "NaN"), r.value, `--${r.name}`);
  }
  for (const s of tokens.shadow.tokens as Token[]) assert.equal(theme.get(`--${s.name}`), s.value, `--${s.name}`);

  const durations = tokens.duration.tokens as Token[];
  for (const d of durations) assert.equal(themeStatic.get(`--transition-${d.name}`), d.value, `--transition-${d.name}`);
  assert.deepEqual([...DURATIONS], durations.map((d) => d.name.replace(/^duration-/, "")), "DURATIONS");

  const easings = tokens.easing.tokens as Token[];
  for (const e of easings) assert.equal(themeStatic.get(`--${e.name}`), e.value, `--${e.name}`);
  assert.deepEqual([...EASINGS], easings.map((e) => e.name.replace(/^ease-/, "")), "EASINGS");
});

test("cn() knows the design system's names", () => {
  const merge = extendTailwindMerge(MERGE_CONFIG);
  // A size and a colour both survive…
  assert.equal(merge("text-body-sm text-muted-foreground"), "text-body-sm text-muted-foreground");
  assert.equal(merge("text-caption text-verdict-ac"), "text-caption text-verdict-ac");
  // …and the later of two of a kind wins.
  assert.equal(merge("text-h1 text-sm"), "text-sm");
  assert.equal(merge("text-sm text-title"), "text-title");
  assert.equal(merge("ease-standard ease-enter"), "ease-enter");
  assert.equal(merge("duration-fast duration-base"), "duration-base");
  assert.equal(merge("duration-fast duration-150"), "duration-150");
});

test("components/ui reads the semantic layer only", () => {
  const dir = new URL("../../components/ui/", import.meta.url);
  const families =
    "slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose|jade|turmeric";
  const rawStep = new RegExp(`\\b[a-z-]+-(?:${families})-\\d{2,3}\\b`, "g");
  for (const file of readdirSync(dir).filter((f) => f.endsWith(".tsx"))) {
    const source = readFileSync(new URL(file, dir), "utf8");
    // A chevron drawn as a data: URL has to spell its colour out; nothing else may.
    const code = source.replace(/url\([^)]*\)/g, "url()");
    assert.deepEqual(code.match(rawStep) ?? [], [], `${file} names a palette step`);
    assert.deepEqual(code.match(/#[0-9a-f]{3,8}\b/gi) ?? [], [], `${file} has a colour of its own`);
    assert.deepEqual(code.match(/\b(?:bg|text|border|ring|outline|fill|stroke)-(?:black|white)\b/g) ?? [], [], `${file} uses black/white`);
    // Line heights under the scale push Vietnamese stacked marks out of the line box.
    assert.doesNotMatch(code, /\bleading-(?:none|tight)\b/, `${file} squeezes the line height`);
  }
});
