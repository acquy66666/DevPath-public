// node --test lib/design/site-states.test.ts  (npm test runs every *.test.ts)
//
// The site's 404, error and loading states follow the reaction map (design
// doc §5) and the design system: Naomi `lost` on a 404, `sorry` on an error
// boundary, none in the instructor and admin areas; skeletons come from
// components/ui/skeleton. These checks read the source, so a new route that
// forgets one of the rules fails here rather than in front of the jury.
import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../../", import.meta.url));
const app = join(root, "app");

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? walk(path) : [path];
  });
}

const files = [...walk(app), ...walk(join(root, "components"))].filter((f) => f.endsWith(".tsx"));
const named = (base: string) => files.filter((f) => f.endsWith(`${sep}${base}`));
const route = (f: string) => relative(app, f).split(sep).join("/");
const read = (f: string) => readFileSync(f, "utf8");
/** The code without its comments, which may well name what the code must not use. */
const code = (f: string) => read(f).replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
const workArea = (f: string) => /\(dashboard\)/.test(f);

test("every not-found page shows Naomi lost", () => {
  const pages = named("not-found.tsx");
  assert.ok(pages.length >= 3, "the site has its own 404 pages");
  for (const page of pages) {
    assert.match(code(page), /<StatePanel[\s\S]*?mood="lost"/, `${route(page)}: no <StatePanel mood="lost">`);
  }
});

test("every error boundary retries, with Naomi sorry outside the work areas", () => {
  const boundaries = [...named("error.tsx"), ...named("global-error.tsx")];
  assert.ok(boundaries.length >= 8, "the site has its own error boundaries");
  for (const file of boundaries) {
    const source = code(file);
    // Next 16.3: `retry` fetches the segment again; `reset` only re-renders
    // a failure that came from the server.
    assert.match(source, /\bretry\b/, `${route(file)}: does not take retry`);
    assert.doesNotMatch(source, /\breset\b/, `${route(file)}: uses reset, which does not fetch again`);
    const mood = workArea(file) ? /mood=\{null\}/ : /mood="sorry"/;
    assert.match(source, mood, `${route(file)}: wrong Naomi for its area`);
  }
});

// The one exception is the instructor overview's "Chào …" (Phase 7 plan,
// group 9: "Nhân vật chỉ ở empty state và lời chào"), and there she stands
// still: opening the overview is not an event.
const GREETING = join("components", "instructor", "instructor-greeting.tsx");

test("Naomi in the instructor and admin areas only in empty states and the greeting", () => {
  for (const file of files.filter((f) => /components[\\/](admin|instructor)[\\/]/.test(f))) {
    if (file.endsWith(GREETING)) {
      assert.match(code(file), /<Mascot\b/, "the greeting has Naomi");
      assert.doesNotMatch(code(file), /<Mascot\b[^>]*\bevent=/, "the greeting's Naomi reacts to nothing");
      continue;
    }
    assert.doesNotMatch(code(file), /<Mascot\b/, `${relative(root, file)}: Naomi outside an empty state`);
  }
});

test("skeletons come from components/ui/skeleton", () => {
  for (const file of files) {
    if (file.endsWith(join("components", "ui", "skeleton.tsx"))) continue;
    assert.doesNotMatch(code(file), /\banimate-pulse\b/, `${relative(root, file)}: hand-drawn skeleton`);
  }
});

test("no loading.tsx above a course page", () => {
  // A loading.tsx wraps every segment below it: in khoa-hoc/ or
  // khoa-hoc/[slug]/ it made the course page stream before it knew the course
  // exists, so a draft answered 200 instead of 404 (gate of Phase 5).
  for (const file of named("loading.tsx")) {
    assert.ok(
      !/^\(marketing\)\/khoa-hoc\/(\[slug\]\/)?loading\.tsx$/.test(route(file)),
      `${route(file)}: turns the course 404 into a 200`,
    );
  }
});
