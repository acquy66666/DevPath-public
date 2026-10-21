// node --test lib/mascot/mascot.test.ts  (npm test runs every *.test.ts)
//
// The choreography is data that names pieces of generated drawings, so most of
// what can go wrong is a name, a number or a colour drifting apart. These
// checks read the drawings (components/mascot/art, from
// docs/ui-ux/mascot/naomi/build.cjs), globals.css and the design-system tokens.
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { test } from "node:test";

import { LINGER_MS, REACTION_MAX_MS, SWAP_MS, reactionFor, typing, type Track } from "./choreography.ts";
import { animated, endsHome, eases, frameCount, offsets, startsAway, toKeyframes, trackEnd } from "./keyframes.ts";
import { MOODS, MOOD_META, PALETTE, type Mood } from "./moods.ts";

const read = (path: string) => readFileSync(new URL(path, import.meta.url), "utf8");
const ART_DIR = new URL("../../components/mascot/art/", import.meta.url);
const art = (mood: Mood) => read(`../../components/mascot/art/${mood}.ts`);
const tokens = JSON.parse(read("../../../docs/ui-ux/design-system/project/tokens.json"));
const globals = read("../../app/globals.css");

/** How many pieces of a drawing answer to these names. */
function matches(svg: string, names: readonly string[]): number {
  return names.reduce((n, name) => n + svg.split(`data-layer="${name}"`).length - 1 + svg.split(`data-part="${name}"`).length - 1, 0);
}

const CSS_PROPERTY = { x: "translate", y: "translate", scale: "scale", scaleX: "scale", scaleY: "scale", rotate: "rotate", opacity: "opacity" } as const;

const all = MOODS.map((mood) => ({ mood, svg: art(mood), reaction: reactionFor(mood, MOOD_META[mood]) }));

test("every mood has one drawing module and a lazy loader for it", () => {
  const files = readdirSync(ART_DIR).filter((f) => f.endsWith(".ts") && f !== "index.ts" && f !== "server.ts");
  assert.deepEqual(files.map((f) => f.replace(/\.ts$/, "")).sort(), [...MOODS].sort());
  const index = read("../../components/mascot/art/index.ts");
  const server = read("../../components/mascot/art/server.ts");
  for (const mood of MOODS) {
    assert.match(index, new RegExp(`"${mood}": \\(\\) => import\\("\\./${mood}"\\)`));
    assert.match(server, new RegExp(`from "\\./${mood}";`), `server.ts reads ${mood}`);
  }
});

test("drawings are decorative, use data-layer and never move a named layer by attribute", () => {
  for (const { mood, svg } of all) {
    assert.match(svg, /aria-hidden="true"/, mood);
    assert.doesNotMatch(svg, / id="/, `${mood}: ids would collide with a second Naomi on the page`);
    assert.doesNotMatch(svg, /data-(layer|part)="[^"]*"[^>]* transform=/, `${mood}: a CSS transform would replace this transform`);
  }
});

test("every track moves something that is in its drawing", () => {
  for (const { mood, svg, reaction } of all) {
    for (const t of reaction.tracks) assert.ok(matches(svg, t.target) > 0, `${mood}: nothing named ${t.target.join(" | ")}`);
  }
  for (const t of typing()) assert.ok(matches(art("grading"), t.target) > 0, `typing: ${t.target}`);
  assert.equal(art("grading").split("data-seg=").length - 1, 5, "grading draws five progress segments");
});

test("keyframes are well formed", () => {
  const easing = { standard: "s", enter: "e", exit: "x", overshoot: "o" };
  for (const { mood, reaction } of all) {
    for (const t of [...reaction.tracks, ...typing()]) {
      const n = frameCount(t);
      const at = offsets(t);
      assert.ok(n >= 2, mood);
      assert.equal(at.length, n, `${mood}: times`);
      assert.equal(at[0], 0, `${mood}: first offset`);
      assert.equal(at[n - 1], 1, `${mood}: last offset`);
      assert.ok(at.every((v, i) => i === 0 || v >= at[i - 1]), `${mood}: offsets go back`);
      assert.equal(eases(t).length, n - 1, `${mood}: one curve per segment`);
      assert.ok(t.at >= 0 && t.duration > 0, mood);
      const frames = toKeyframes(t, easing);
      assert.equal(frames.length, n);
      assert.equal(frames[n - 1].easing, undefined);
    }
  }
});

test("a reaction ends within duration-mascot, and the cross-fade is duration-base", () => {
  const ms = (name: string) => parseInt(tokens.duration.tokens.find((t: { name: string }) => t.name === name).value, 10);
  assert.equal(REACTION_MAX_MS, ms("duration-mascot"));
  assert.equal(SWAP_MS, ms("duration-base"));
  assert.ok(LINGER_MS < REACTION_MAX_MS);
  for (const { mood, svg, reaction } of all) {
    const end = Math.max(...reaction.tracks.map((t) => trackEnd(t, matches(svg, t.target))));
    assert.ok(end <= REACTION_MAX_MS, `${mood} ends at ${end} ms`);
  }
});

test("every piece ends where the drawing has it", () => {
  // The still pose is the drawing itself: reduced motion, a reaction cut short
  // and the end of a `hold` reaction must all look the same.
  for (const { mood, reaction } of all) for (const t of reaction.tracks) assert.ok(endsHome(t), `${mood}: ${t.target.join(",")} does not come back`);
});

test("no two tracks fight over a property, or a pivot, of the same piece", () => {
  type Use = { from: number; to: number; origin: string; track: Track };
  for (const { mood, svg, reaction } of [...all, { mood: "grading (typing)", svg: art("grading"), reaction: { tracks: typing() } }]) {
    const uses = new Map<string, Use[]>();
    for (const t of reaction.tracks) {
      // A track that starts away from the drawing holds its first frame from time 0.
      const from = startsAway(t) ? 0 : t.at;
      const to = trackEnd(t, matches(svg, t.target));
      const props = new Set(animated(t).map((p) => CSS_PROPERTY[p]));
      for (const name of t.target) {
        for (const prop of props) {
          const key = `${name}.${prop}`;
          for (const u of uses.get(key) ?? []) {
            assert.ok(to <= u.from || from >= u.to, `${mood}: two tracks animate ${prop} of ${name} at once`);
          }
          uses.set(key, [...(uses.get(key) ?? []), { from, to, origin: "", track: t }]);
        }
        if ([...props].some((p) => p !== "opacity")) {
          const key = `${name}.origin`;
          const origin = JSON.stringify(t.origin);
          for (const u of uses.get(key) ?? []) assert.equal(u.origin, origin, `${mood}: ${name} turns around two pivots`);
          uses.set(key, [...(uses.get(key) ?? []), { from, to, origin, track: t }]);
        }
      }
    }
  }
});

test("only a passing gesture goes back to rest; every other mood keeps its pose", () => {
  // Going back to rest drops the mood's props and framing; see `Settle`.
  const toRest = all.filter((m) => m.reaction.settle === "rest").map((m) => m.mood);
  assert.deepEqual(toRest, ["wave"]);
  // `wave` is drawn at rest's size and place, so the cross-fade does not jump.
  assert.deepEqual(MOOD_META.wave.ground, MOOD_META.rest.ground);
  assert.deepEqual(MOOD_META.wave.shadow, MOOD_META.rest.shadow);
});

test("the colours the drawings read are the design-system tokens, scoped in globals.css", () => {
  const values = Object.fromEntries(tokens.color.tokens.map((t: { name: string; value: string }) => [t.name, t.value.toLowerCase()]));
  for (const [name, hex] of Object.entries(PALETTE)) assert.equal(hex, values[name], `${name} in tokens.json`);

  const block = /\[data-mascot\]\s*\{([^}]*)\}/.exec(globals);
  assert.ok(block, "globals.css has the [data-mascot] palette");
  const scoped = Object.fromEntries([...block[1].matchAll(/--color-([a-z]+-\d+):\s*(#[0-9a-f]{6});/g)].map((m) => [m[1], m[2]]));
  assert.deepEqual(scoped, PALETTE);

  for (const { mood, svg } of all) {
    for (const [, name] of svg.matchAll(/var\(--color-([a-z0-9-]+)\)/g)) assert.ok(name in PALETTE, `${mood} reads ${name}`);
    assert.doesNotMatch(svg, /#[0-9a-f]{3,6}\b/i, `${mood}: a colour outside the tokens`);
  }
});

test("the curves in globals.css are the design-system easing tokens", () => {
  for (const t of tokens.easing.tokens as { name: string; value: string }[]) {
    const m = new RegExp(`--${t.name}:\\s*([^;]+);`).exec(globals);
    assert.ok(m, `globals.css defines --${t.name}`);
    assert.equal(m[1].trim(), t.value);
  }
});
