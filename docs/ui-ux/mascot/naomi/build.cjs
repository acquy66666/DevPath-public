// Naomi, the DevPath gecko. Every drawing of the model sheet and of the
// expression set is generated here from one set of parts, so a change to a
// part (the eye, the hand, the tail) reaches every mood at once, and every
// file has the same named layers for the animation component to drive.
//
//   node docs/ui-ux/mascot/naomi/build.cjs
//
// Writes views/, moods/, layers/ and naomi.json next to this file. Colours are
// named by design-system token and resolved from tokens.json; a name that is not
// a token stops the build. The files it writes are output: change this script,
// not the SVGs. Rules and checks: ../README.md, ../check/naomi.cjs.
"use strict";
const fs = require("fs");
const path = require("path");

const HERE = __dirname;
const REPO = path.join(HERE, "..", "..", "..", "..");
const TOKENS = path.join(REPO, "docs", "ui-ux", "design-system", "project", "tokens.json");

const HEX = Object.fromEntries(
  JSON.parse(fs.readFileSync(TOKENS, "utf8"))
    .color.tokens.filter((t) => /^#[0-9a-f]{6}$/i.test(t.value))
    .map((t) => [t.name, t.value.toLowerCase()])
);
// Two outputs from the same parts. The SVG files under docs/ are images (hex
// colours, `id` per layer). The web drawings for components/mascot (WEB) name
// colours as CSS variables, so the page's tokens paint them, and call layers by
// `data-layer`: a page can hold two Naomis, and ids must be unique on a page.
let WEB = false;
const USED = new Set(); // colour tokens the web drawings read
const C = (name) => {
  if (!HEX[name]) throw new Error(`not a colour token: ${name}`);
  if (!WEB) return HEX[name];
  USED.add(name);
  return `var(--color-${name})`;
};

// Naomi's own palette, by role.
const INK = "jade-900"; // every outline
const SKIN = "jade-500"; // body, head, limbs, tail
const BELLY = "jade-100";
const SPOT = "jade-700"; // the leopard spots that keep her from reading as a frog
const WHITE = "slate-0";
const IRIS = "turmeric-300"; // the only turmeric on her body: never the mouth, hands or feet
const TONGUE = "rose-500";
const BLUSH = "rose-200";
const SHADOW = "slate-100";
const SWEAT = "blue-200";

// ---------------------------------------------------------------- markup
const num = (v) => (typeof v === "number" ? String(Math.round(v * 100) / 100) : v);
function el(tag, attrs = {}, kids) {
  const a = Object.entries(attrs)
    .filter(([, v]) => v !== undefined && v !== null && v !== false)
    .map(([k, v]) => ` ${k}="${num(v)}"`)
    .join("");
  const inner = kids === undefined ? "" : [].concat(kids).flat(Infinity).filter(Boolean).join("");
  return inner ? `<${tag}${a}>${inner}</${tag}>` : `<${tag}${a}/>`;
}
// A named element. On the web a CSS transform replaces the SVG `transform`
// attribute instead of adding to it, so a named group never carries one there:
// its placement moves to an inner group and the name stays free to animate.
function named(tag, id, attrs = {}, kids) {
  if (!WEB) return el(tag, { id, ...attrs }, kids);
  if (tag !== "g" || !attrs.transform) return el(tag, { "data-layer": id, ...attrs }, kids);
  const { transform, ...rest } = attrs;
  return el("g", { "data-layer": id, ...rest }, [el("g", { transform }, kids === undefined ? [] : kids)]);
}
const g = (id, kids, attrs = {}) => named("g", id, attrs, kids);
// A small piece the component moves on its own (a sparkle, a drop, a Z). The
// images have no wrapper; on the web it is a group with nothing on it to move.
const part = (name, kids) => (WEB ? el("g", { "data-part": name }, kids) : kids);
const P = (pts) => pts.map(([x, y]) => `${num(x)} ${num(y)}`).join(" ");

// A shape is [tag, attrs] so the same geometry can be drawn twice.
const circle = (cx, cy, r) => ["circle", { cx, cy, r }];
const ellipse = (cx, cy, rx, ry, rot) => ["ellipse", { cx, cy, rx, ry, transform: rot ? `rotate(${rot} ${num(cx)} ${num(cy)})` : undefined }];
const shape = (d) => ["path", { d }];
const rect = (x, y, w, h, rx = 0, rot) => ["rect", { x, y, width: w, height: h, rx, transform: rot ? `rotate(${rot[0]} ${rot[1]} ${rot[2]})` : undefined }];
const draw = ([tag, attrs], extra = {}) => el(tag, { ...attrs, ...extra });

// Outline only on the outer edge: the shapes once in ink with a wide stroke,
// then again in their colour with no stroke. Joined shapes share one outline.
function solid(shapes, fill, w = 9) {
  return [
    el("g", { fill: C(INK), stroke: C(INK), "stroke-width": w, "stroke-linejoin": "round" }, shapes.map((s) => draw(s))),
    el("g", { fill: C(fill) }, shapes.map((s) => draw(s))),
  ];
}
// Limbs and tail are strokes: a wide ink stroke under a narrower coloured one.
function limb(d, w = 8, color = SKIN, cap = "round", outline = 9) {
  const base = { d, fill: "none", "stroke-linecap": cap, "stroke-linejoin": "round" };
  return [el("path", { ...base, stroke: C(INK), "stroke-width": w + outline }), el("path", { ...base, stroke: C(color), "stroke-width": w })];
}
const line = (d, color = INK, w = 2.5, extra = {}) =>
  el("path", { d, fill: "none", stroke: C(color), "stroke-width": w, "stroke-linecap": "round", "stroke-linejoin": "round", ...extra });
const dots = (list, color = SPOT) => list.map(([x, y, r]) => el("circle", { cx: x, cy: y, r, fill: C(color) }));
const mirrorX = (x) => 200 - x;
// Mirror a path made of absolute M/L/C/Q/S/T commands and coordinate pairs.
function mirrorD(d) {
  let i = 0;
  return d.replace(/-?\d*\.?\d+(?:e-?\d+)?/g, (m) => (i++ % 2 === 0 ? num(mirrorX(Number(m))) : m));
}

// ---------------------------------------------------------------- props and effects
const SPARKLE = "M0 -9 C1 -3 3 -1 9 0 C3 1 1 3 0 9 C-1 3 -3 1 -9 0 C-3 -1 -1 -3 0 -9 Z";
const sparkle = (x, y, s = 1, color = "turmeric-300") =>
  part("spark", el("path", { d: SPARKLE, transform: `translate(${num(x)} ${num(y)}) scale(${s})`, fill: C(color), stroke: C(INK), "stroke-width": num(1.8 / s), "stroke-linejoin": "round" }));
function starPath(cx, cy, R, r, rot = -90, n = 5) {
  const pts = [];
  for (let i = 0; i < n * 2; i++) {
    const a = ((rot + (i * 180) / n) * Math.PI) / 180;
    const rr = i % 2 ? r : R;
    pts.push([cx + rr * Math.cos(a), cy + rr * Math.sin(a)]);
  }
  return `M${P(pts)} Z`;
}
const star = (cx, cy, R, color, sw = 1.6) =>
  el("path", { d: starPath(cx, cy, R, R * 0.48), fill: C(color), stroke: C(INK), "stroke-width": sw, "stroke-linejoin": "round" });
const drop = (x, y, s = 1, color = SWEAT) =>
  part("drop", el("path", { d: "M0 -8 C-5 0 -5 6 0 6 C5 6 5 0 0 -8 Z", transform: `translate(${num(x)} ${num(y)}) scale(${s})`, fill: C(color), stroke: C(INK), "stroke-width": num(2.4 / s), "stroke-linejoin": "round" }));
const heartPath = "M0 9 C-14 0 -12 -11 -5 -11 C-2 -11 0 -9 0 -6 C0 -9 2 -11 5 -11 C12 -11 14 0 0 9 Z";
function bug(x, y, rot = 0, { wings = false } = {}) {
  return part("bug", el("g", { transform: `translate(${x} ${y}) rotate(${rot})` }, [
    wings && el("ellipse", { cx: -9, cy: -3, rx: 8, ry: 4.5, transform: "rotate(-30 -9 -3)", fill: C(WHITE), stroke: C(INK), "stroke-width": 2 }),
    wings && el("ellipse", { cx: 9, cy: -3, rx: 8, ry: 4.5, transform: "rotate(30 9 -3)", fill: C(WHITE), stroke: C(INK), "stroke-width": 2 }),
    !wings && line("M-8 -2 L-13 -5 M-9 3 L-14 3 M8 -2 L13 -5 M9 3 L14 3", INK, 2),
    line("M-2 -12 Q-4 -17 -8 -17 M2 -12 Q4 -17 8 -17", INK, 1.8),
    el("circle", { cx: 0, cy: -8, r: 5, fill: C(INK) }),
    el("circle", { cx: 0, cy: 1, r: 9, fill: C("red-500"), stroke: C(INK), "stroke-width": 2.5 }),
    line("M0 -8 L0 10", INK, 2),
    dots([[-4.5, -1, 1.8], [4.5, -1, 1.8], [-4, 5, 1.8], [4, 5, 1.8]], INK),
  ]));
}
// The letter Z as strokes (no text in the drawings: an <img> SVG has no fonts).
const zed = (x, y, s, color = "slate-500") => part("zed", line(`M${x} ${y} L${x + 8 * s} ${y} L${x} ${y + 8 * s} L${x + 8 * s} ${y + 8 * s}`, color, 2.4));
const motion = (d) => part("whoosh", line(d, INK, 2.5));

// ---------------------------------------------------------------- the body, front
// Naomi's right side is on the viewer's left when she faces us. `right`/`left`
// in layer names are always hers.
const EYE = { right: [62, 66], left: [138, 66] };
const HEAD_SPOTS = [[100, 52, 4.4], [88, 58, 2.6], [113, 57, 3], [102, 64, 2]];
const BODY_D = "M72 120 C62 150 66 178 100 179 C134 178 138 150 128 120 Z";
const BODY_SPOTS = [[86, 133, 3], [115, 138, 3.2], [102, 130, 2]];
const TAIL = {
  coil: "M116 166 C130 174 146 172 160 172 C174.4 172 186 160.4 186 146 C186 131.6 174.4 120 160 120 C145.6 120 134 131.6 134 146",
  tip: "M134 146 C134 156 141 162 149 162 C156 162 160 156 157 151",
  spots: [[186, 146, 2.8], [180, 129, 2.5], [164, 120.5, 2.3], [146, 171, 2.5]],
};

function tail({ coil = TAIL.coil, tip = TAIL.tip, spots = TAIL.spots, transform } = {}) {
  return el("g", { transform }, [limb(coil, 11, SKIN, "butt"), limb(tip, 7.5, SKIN, "round", 8.5), g("tail-spots", dots(spots))]);
}

function foot(id, [cx, cy], side, { rot = 0, toes = [[-14, 4], [-5, 10], [7, 9]], sole = [14, 8], toeR = 5 } = {}) {
  const s = side === "right" ? 1 : -1;
  const shapes = [...toes.map(([x, y]) => circle(cx + x * s, cy + y, toeR)), ellipse(cx, cy, sole[0], sole[1])];
  return g(id, solid(shapes, SKIN), { transform: rot ? `rotate(${rot} ${cx} ${cy})` : undefined });
}
const feetFront = (o = {}) => [foot("foot-right", o.right || [80, 180], "right", o.rightOpt), foot("foot-left", o.left || [120, 180], "left", o.leftOpt)];

function bodyFront({ d = BODY_D, belly = [100, 158, 19, 17], spots = BODY_SPOTS } = {}) {
  return [solid([shape(d)], SKIN), named("ellipse", "belly", { cx: belly[0], cy: belly[1], rx: belly[2], ry: belly[3], fill: C(BELLY) }), g("body-spots", dots(spots))];
}

function headFront({ extra = [], spots = HEAD_SPOTS, nostrils = [[94, 84], [106, 84]], cheeks = false } = {}) {
  const shapes = [ellipse(100, 82, 58, 40), circle(...EYE.right, 21), circle(...EYE.left, 21), ...extra];
  return [
    g("head-shape", solid(shapes, SKIN)),
    g("head-spots", dots(spots)),
    g("nostrils", dots(nostrils.map(([x, y]) => [x, y, 1.6]), INK)),
    cheeks ? g("cheeks", [el("ellipse", { cx: 50, cy: 96, rx: 8, ry: 4.6, fill: C(BLUSH) }), el("ellipse", { cx: 150, cy: 96, rx: 8, ry: 4.6, fill: C(BLUSH) })]) : "",
  ];
}

// Hands: four round toe pads fanned around the wrist, pointing along `dir` (degrees).
function pads(wx, wy, dir, { spread = 1, scale = 1 } = {}) {
  const dist = [10.5, 13, 13.5, 12];
  return [-60, -20, 20, 60].map((o, i) => {
    const a = ((dir + o * spread) * Math.PI) / 180;
    return circle(wx + dist[i] * scale * Math.cos(a), wy + dist[i] * scale * Math.sin(a), 4.2 * scale);
  });
}
function fist(x, y, dir = 0) {
  const a = (dir * Math.PI) / 180;
  const ox = Math.cos(a) * 4, oy = Math.sin(a) * 4;
  return [
    ...solid([circle(x + ox, y + oy, 9.5)], SKIN, 7),
    line(`M${num(x + ox - 5)} ${num(y + oy + 1)} Q${num(x + ox)} ${num(y + oy + 5)} ${num(x + ox + 5)} ${num(y + oy + 1)}`, INK, 2),
  ];
}
// An arm: a stroke from the shoulder plus a hand, and an optional thing held in
// it (`held`, drawn under the fingers unless heldFront).
function arm(id, a) {
  const { d, wrist, dir = 90, hand = "pads", spread, held, heldFront = false, w = 8 } = a;
  const kids = [g(`${id}-limb`, limb(d, w))];
  if (held && !heldFront) kids.push(g(`${id}-held`, held));
  if (hand === "pads") kids.push(g(`${id}-hand`, solid(pads(wrist[0], wrist[1], dir, { spread }), SKIN, 7)));
  if (hand === "fist") kids.push(g(`${id}-hand`, fist(wrist[0], wrist[1], dir)));
  if (held && heldFront) kids.push(g(`${id}-held`, held));
  return kids;
}
// Arms are written for Naomi's right (viewer's left) and mirrored for her left,
// held thing included. `mirror: false` means the spec is already where it goes
// (a tick or a card must not come out reversed).
const mirrorArm = (a) =>
  a.mirror === false
    ? a
    : {
        ...a,
        d: mirrorD(a.d),
        wrist: [mirrorX(a.wrist[0]), a.wrist[1]],
        dir: 180 - (a.dir ?? 90),
        held: a.held && el("g", { transform: "matrix(-1 0 0 1 200 0)" }, a.held),
      };
const ARM_REST = { d: "M74 128 C70 140 66 150 63 158", wrist: [63, 158], dir: 108 };

// ---------------------------------------------------------------- eyes
// The top lid is the part of the eye above a line through (cx, cy + h) that
// tilts `a` degrees; drawn in skin with the eye's own outline.
function lidD(cx, cy, h, a, top = true, R = 15.5) {
  const m = Math.tan((a * Math.PI) / 180);
  const A = 1 + m * m, B = 2 * h * m, K = h * h - R * R;
  const disc = B * B - 4 * A * K;
  if (disc <= 0) return null;
  const t1 = (-B - Math.sqrt(disc)) / (2 * A), t2 = (-B + Math.sqrt(disc)) / (2 * A);
  const p1 = [cx + t1, cy + h + m * t1], p2 = [cx + t2, cy + h + m * t2];
  const large = top ? (h > 0 ? 1 : 0) : h < 0 ? 1 : 0;
  return `M${P([p1])} A${R} ${R} 0 ${large} ${top ? 1 : 0} ${P([p2])} Z`;
}
const lidShape = (d) => el("path", { d, fill: C(SKIN), stroke: C(INK), "stroke-width": 3, "stroke-linejoin": "round" });

function spiralD(cx, cy, R = 11, turns = 2.6) {
  const pts = [];
  const steps = 48;
  for (let i = 0; i <= steps; i++) {
    const t = (i / steps) * turns * 2 * Math.PI;
    const r = (R * i) / steps;
    pts.push([cx + r * Math.cos(t), cy + r * Math.sin(t)]);
  }
  return `M${P(pts)}`;
}

// One eye. kind: open | wide | dot | star | spiral | happy | closed | squeeze.
// o.look moves the iris; o.lid / o.lower = { h, a } (a as for Naomi's right
// eye, mirrored for her left so expressions stay symmetric).
function eye(side, kind = "open", o = {}) {
  const [cx, cy] = o.at || EYE[side];
  const s = side === "right" ? 1 : -1;
  const white = (r = 15.5) => el("circle", { cx, cy, r, fill: C(WHITE), stroke: C(INK), "stroke-width": 3 });
  let [lx, ly] = o.look || [2, 1];
  const len = Math.hypot(lx, ly);
  const max = kind === "wide" ? 7 : 4.5;
  if (len > max) [lx, ly] = [(lx * max) / len, (ly * max) / len];
  const ix = cx + lx, iy = cy + ly;
  let markup;
  switch (kind) {
    case "open":
      markup = [
        white(),
        el("circle", { cx: ix, cy: iy, r: 11, fill: C(IRIS) }),
        el("ellipse", { cx: ix + 1, cy: iy, rx: 5.2, ry: 8.5, fill: C(INK) }),
        el("circle", { cx: ix + 4, cy: iy - 6, r: 3.2, fill: C(WHITE) }),
        o.sparkle && el("circle", { cx: ix - 3.5, cy: iy + 5.5, r: 1.7, fill: C(WHITE) }),
      ];
      break;
    case "wide":
      markup = [
        white(16.5),
        el("circle", { cx: ix, cy: iy, r: 7, fill: C(IRIS) }),
        el("circle", { cx: ix, cy: iy, r: 3.4, fill: C(INK) }),
        el("circle", { cx: ix + 2.6, cy: iy - 3, r: 1.6, fill: C(WHITE) }),
      ];
      break;
    case "dot":
      markup = [white(), el("circle", { cx: ix, cy: iy, r: 2.8, fill: C(INK) })];
      break;
    case "star":
      markup = [white(), star(ix, iy + 0.5, 12, IRIS, 1.8), el("circle", { cx: ix + 4.5, cy: iy - 5, r: 2.2, fill: C(WHITE) })];
      break;
    case "spiral":
      markup = [white(), line(spiralD(cx, cy, 11.5, o.turns || 2.6), INK, 2.4)];
      break;
    case "happy":
      markup = [line(`M${cx - 11} ${cy + 5} Q${cx} ${cy - 12} ${cx + 11} ${cy + 5}`, INK, 5)];
      break;
    case "closed":
      markup = [line(`M${cx - 11} ${cy - 1} Q${cx} ${cy + 9} ${cx + 11} ${cy - 1}`, INK, 5)];
      break;
    case "squeeze":
      markup = [line(`M${cx - 8 * s} ${cy - 8} L${cx + 7 * s} ${cy} L${cx - 8 * s} ${cy + 8}`, INK, 5)];
      break;
    default:
      throw new Error(`eye kind ${kind}`);
  }
  const lids = [];
  if (o.lid) lids.push(lidShape(lidD(cx, cy, o.lid.h, o.lid.a * s, true)));
  if (o.lower) lids.push(lidShape(lidD(cx, cy, o.lower.h, (o.lower.a || 0) * s, false)));
  return { eye: markup, lid: lids };
}

// ---------------------------------------------------------------- mouths
function mouth(kind, { dx = 0, dy = 0 } = {}) {
  const t = dx || dy ? `translate(${dx} ${dy})` : undefined;
  const fillInk = (d) => el("path", { d, fill: C(INK), stroke: C(INK), "stroke-width": 4, "stroke-linejoin": "round" });
  const tongue = (d) => el("path", { d, fill: C(TONGUE) });
  const m = {
    smile: () => line("M76 98 C88 108 112 108 124 98", INK, 4),
    small: () => line("M86 100 C93 106 107 106 114 100", INK, 4),
    grin: () => [fillInk("M78 96 C84 120 116 120 122 96 C108 101 92 101 78 96 Z"), tongue("M90 111 C94 105 106 105 110 111 C106 115 94 115 90 111 Z")],
    open: () => [fillInk("M86 98 C88 112 112 112 114 98 C106 100 94 100 86 98 Z"), tongue("M93 107.5 C96 104 104 104 107 107.5 C104 110 96 110 93 107.5 Z")],
    o: () => el("ellipse", { cx: 100, cy: 102, rx: 4.5, ry: 5.5, fill: C(INK) }),
    bigO: () => [el("ellipse", { cx: 100, cy: 105, rx: 8, ry: 10, fill: C(INK) }), tongue("M94 111 C96 108 104 108 106 111 C104 113.5 96 113.5 94 111 Z")],
    yawn: () => [el("ellipse", { cx: 100, cy: 106, rx: 10, ry: 13, fill: C(INK) }), el("ellipse", { cx: 100, cy: 113, rx: 6, ry: 3.6, fill: C(TONGUE) })],
    wavy: () => line("M84 104 C89 99 94 107 100 103 C106 99 111 107 116 102", INK, 4),
    flat: () => line("M90 103 L110 103", INK, 4),
    frown: () => line("M86 107 C94 99 106 99 114 107", INK, 4),
    smug: () => line("M82 99 C92 106 108 106 120 94", INK, 4),
    focus: () => [
      el("path", { d: "M105 102 C106 109 113 110 114 103 Z", fill: C(TONGUE), stroke: C(INK), "stroke-width": 2.2, "stroke-linejoin": "round" }),
      line("M88 102 C96 104 106 104 114 101", INK, 4),
    ],
    blep: () => [
      el("path", { d: "M99 103 C99 112 108 113 109 104 Z", fill: C(TONGUE), stroke: C(INK), "stroke-width": 2.2, "stroke-linejoin": "round" }),
      line("M84 104 C89 99 94 107 100 103 C106 99 111 106 116 101", INK, 4),
    ],
    awkward: () => line("M85 103 C91 107 97 107 103 103 C107 100 112 101 116 105", INK, 4),
    pressed: () => line("M92 104 Q96 100 100 104 Q104 100 108 104", INK, 3.6),
    side: () => line("M92 105 Q101 101 112 103", INK, 4),
  };
  return el("g", { transform: t }, [].concat(m[kind]()));
}

// ---------------------------------------------------------------- a pose
// Layer order inside <g id="naomi">, back to front. Arms can move behind the
// body ("behind"), behind held props ("back"), or in front of the face ("front").
const LAYERS = ["fx-back", "tail", "feet", "body", "props", "arm-right", "arm-left", "head", "eyes", "eyelids", "mouth", "props-head", "fx"];
const HEAD_LAYERS = new Set(["head", "eyes", "eyelids", "mouth", "props-head"]);

class Pose {
  constructor() {
    this.shadow = { cx: 100, cy: 194, rx: 40, ry: 4.5 };
    this.scene = [];
    this.naomi = undefined; // transform of the whole character
    this.headT = undefined; // transform shared by the head layers
    this.z = { "arm-right": "mid", "arm-left": "mid" };
    this.L = {
      "fx-back": [],
      tail: tail(),
      feet: feetFront(),
      body: bodyFront(),
      props: [],
      "arm-right": arm("arm-right", ARM_REST),
      "arm-left": arm("arm-left", mirrorArm(ARM_REST)),
      head: headFront(),
      eyes: [],
      eyelids: [],
      mouth: mouth("smile"),
      "props-head": [],
      fx: [],
    };
    this.eyes("open");
  }
  eyes(kind, o = {}, kindLeft = kind, oLeft = o) {
    const r = eye("right", kind, o), l = eye("left", kindLeft, oLeft);
    this.L.eyes = [g("eye-right", r.eye), g("eye-left", l.eye)];
    this.L.eyelids = [r.lid.length ? g("lid-right", r.lid) : "", l.lid.length ? g("lid-left", l.lid) : ""];
    return this;
  }
  arm(side, a, z) {
    const id = `arm-${side}`;
    this.L[id] = arm(id, side === "left" ? mirrorArm(a) : a);
    if (z) this.z[id] = z;
    return this;
  }
  // Same arm on both sides, mirrored.
  arms(a, z) {
    return this.arm("right", a, z).arm("left", a, z);
  }
  set(layer, markup) {
    if (!(layer in this.L)) throw new Error(`no layer ${layer}`);
    this.L[layer] = markup;
    return this;
  }
  add(layer, markup) {
    this.L[layer] = [].concat(this.L[layer], markup);
    return this;
  }
  order() {
    const out = [];
    const armsAt = (where) => ["arm-right", "arm-left"].filter((a) => this.z[a] === where);
    for (const n of LAYERS) {
      if (n === "body") out.push(...armsAt("behind"));
      if (n === "props") {
        out.push(n, ...armsAt("mid"));
        continue;
      }
      if (n === "arm-right" || n === "arm-left") continue;
      if (n === "fx") out.push(...armsAt("front"));
      out.push(n);
    }
    // "back" arms go right before props
    const i = out.indexOf("props");
    out.splice(i, 0, ...armsAt("back"));
    return out;
  }
  render(label, mood, only) {
    const show = (n) => !only || only === n;
    const layers = this.order().map((n) => {
      const kids = show(n) ? [].concat(this.L[n]).flat(Infinity).filter(Boolean) : [];
      const attrs = { id: n, transform: HEAD_LAYERS.has(n) ? this.headT : undefined };
      if (!kids.length) return `    ${el("g", attrs)}`;
      return `    ${el("g", attrs).replace(/\/>$/, ">")}\n${kids.map((k) => `      ${k}`).join("\n")}\n    </g>`;
    });
    const sh = this.shadow;
    const shadow = sh && show("shadow") ? el("ellipse", { id: "shadow", cx: sh.cx, cy: sh.cy, rx: sh.rx, ry: sh.ry, fill: C(SHADOW) }) : el("g", { id: "shadow" });
    const scene = show("scene") && this.scene.length ? `<g id="scene">\n${[].concat(this.scene).flat(Infinity).filter(Boolean).map((k) => `    ${k}`).join("\n")}\n  </g>` : el("g", { id: "scene" });
    return [
      `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" role="img" aria-label="${label}" data-mood="${mood}">`,
      `  <!-- Generated by docs/ui-ux/mascot/naomi/build.cjs. Edit the script, not this file. -->`,
      `  ${shadow}`,
      `  ${scene}`,
      `  ${el("g", { id: "naomi", transform: this.naomi }).replace(/\/>$/, ">")}`,
      ...layers,
      `  </g>`,
      `</svg>`,
      "",
    ].join("\n");
  }
  // The drawing for components/mascot: one line, decorative (the component
  // carries the label), allowed to spill out of the viewBox when Naomi jumps.
  renderWeb(mood) {
    const kids = (n) => [].concat(this.L[n]).flat(Infinity).filter(Boolean);
    const layers = this.order().map((n) => named("g", n, { transform: HEAD_LAYERS.has(n) ? this.headT : undefined }, kids(n)));
    const sh = this.shadow;
    return el("svg", { xmlns: "http://www.w3.org/2000/svg", viewBox: "0 0 200 200", width: "100%", height: "100%", overflow: "visible", "aria-hidden": "true", focusable: "false", "data-mood": mood }, [
      sh ? named("ellipse", "shadow", { cx: sh.cx, cy: sh.cy, rx: sh.rx, ry: sh.ry, fill: C(SHADOW) }) : named("g", "shadow"),
      named("g", "scene", {}, [].concat(this.scene).flat(Infinity).filter(Boolean)),
      named("g", "naomi", { transform: this.naomi }, layers),
    ]);
  }
  // Where the component pivots the whole character and its shadow, in the
  // coordinates of the <svg>: her feet (drawing point 100,190) moved by the
  // pose's own transform, and the centre of the shadow.
  anchors() {
    const sh = this.shadow;
    return { ground: applyTransform(this.naomi, [100, 190]), shadow: sh ? [sh.cx, sh.cy] : null };
  }
}

// Apply an SVG transform list (translate / scale / rotate only) to a point.
function applyTransform(list, [x, y]) {
  if (!list) return [x, y];
  const ops = [...list.matchAll(/(translate|scale|rotate)\(([^)]*)\)/g)].map((m) => [m[1], m[2].trim().split(/[\s,]+/).map(Number)]);
  if (ops.map((o) => `${o[0]}(${o[1].join(" ")})`).join(" ") !== list.replace(/\s+/g, " ").trim()) throw new Error(`transform not understood: ${list}`);
  // The rightmost operation applies first.
  for (const [op, a] of ops.reverse()) {
    if (op === "translate") [x, y] = [x + a[0], y + (a[1] ?? 0)];
    else if (op === "scale") [x, y] = [x * a[0], y * (a[1] ?? a[0])];
    else {
      const [deg, cx = 0, cy = 0] = a;
      const r = (deg * Math.PI) / 180;
      const dx = x - cx, dy = y - cy;
      [x, y] = [cx + dx * Math.cos(r) - dy * Math.sin(r), cy + dx * Math.sin(r) + dy * Math.cos(r)];
    }
  }
  return [Math.round(x * 100) / 100, Math.round(y * 100) / 100];
}

// ---------------------------------------------------------------- the moods
// Section 5 of docs/ui-ux/thiet-ke-nang-cap-ui-ux.md, plus `rest`.
const MOODS = [];
function mood(name, event, where, label, build) {
  MOODS.push({ name, event, where, label, build });
}

mood("rest", "Tư thế nghỉ — lúc chờ, và sau cái vẫy tay của wave (mood khác giữ dáng của mình)", "Mọi nơi có nhân vật", "Naomi ngồi nghỉ, mỉm cười", () => new Pose());

mood("grading", "Đang chấm, WebSocket báo “test k/n”", "Trang nộp bài", "Naomi gõ laptop, thanh tiến độ chấm bài", () => {
  const p = new Pose().eyes("open", { look: [0, 4.5], lid: { h: -5, a: 0 } }).set("mouth", mouth("focus"));
  p.arms({ d: "M74 128 C72 136 74 142 82 148", wrist: [82, 148], dir: 60 }, "back");
  // Five segments, three lit in the drawing. On the web the component lights
  // them from the test count (`data-seg`), using these two colours.
  const seg = [0, 1, 2, 3, 4].map((i) => el("rect", { x: 70 + i * 12.4, y: 165, width: 9.6, height: 5.5, rx: 2.75, fill: C(i < 3 ? "green-600" : "slate-300"), "data-seg": WEB ? i : undefined }));
  p.set("props", [
    g("laptop-base", solid([rect(50, 178, 100, 9, 4.5)], "slate-300", 7)),
    g("laptop-lid", solid([rect(58, 134, 84, 46, 7)], "slate-100", 7)),
    g("laptop-logo", line("M92 146 L86 151.5 L92 157 M108 146 L114 151.5 L108 157 M103.5 144 L96.5 159", "jade-600", 3)),
    g("progress", seg),
  ]);
  p.set("fx", [motion("M52 128 L45 122"), motion("M148 128 L155 122"), motion("M55 120 L52 113")]);
  return p;
});

mood("celebrate", "Verdict AC 100/100", "Trang nộp bài", "Naomi nhảy lên, giơ con bọ vừa bắt được", () => {
  const p = new Pose().eyes("happy").set("mouth", mouth("grin"));
  p.naomi = "translate(0 -8)";
  p.shadow = { cx: 100, cy: 194, rx: 32, ry: 4 };
  p.set("head", headFront({ cheeks: true }));
  p.arm("right", { d: "M74 126 C56 126 42 118 36 104", wrist: [36, 104], dir: -115 });
  p.arm("left", { d: "M74 126 C54 120 42 102 38 84", wrist: [38, 84], dir: -100, held: bug(30, 52, 18) });
  p.scene = [sparkle(22, 60), sparkle(104, 14, 0.8), sparkle(188, 118, 0.7)];
  return p;
});

mood("partial", "AC một phần / WA", "Trang nộp bài", "Naomi gãi đầu nhìn con bọ bay mất", () => {
  const p = new Pose().eyes("open", { look: [4, 2], lid: { h: -4, a: 0 } }).set("mouth", mouth("wavy"));
  p.arm("right", { d: "M74 128 C54 128 40 116 38 100", wrist: [38, 100], dir: -100 }, "front");
  p.scene = [part("trail", line("M148 46 C154 34 162 42 168 34", INK, 2.2, { "stroke-dasharray": "0.5 6" })), bug(178, 26, 24, { wings: true })];
  p.set("fx", [drop(30, 60)]);
  return p;
});

mood("sleepy", "Verdict TLE (quá thời gian)", "Trang nộp bài", "Naomi ngáp cạnh đồng hồ cát", () => {
  const p = new Pose().eyes("closed").set("mouth", mouth("yawn"));
  p.headT = "rotate(-6 100 122)";
  p.arm("right", { d: "M74 128 C64 126 62 118 68 112", wrist: [68, 112], dir: -30 }, "front");
  p.scene = g("hourglass", [
    el("path", { d: "M20 146 C20 160 27 162 27 166 C27 170 20 172 20 186 L40 186 C40 172 33 170 33 166 C33 162 40 160 40 146 Z", fill: C(WHITE), stroke: C(INK), "stroke-width": 2.6, "stroke-linejoin": "round" }),
    el("path", { d: "M23 185 C24 178 28 175 30 175 C32 175 36 178 37 185 Z", fill: C("amber-500") }),
    el("path", { d: "M24 151 L36 151 C35 156 32 158 30 160 C28 158 25 156 24 151 Z", fill: C("amber-500") }),
    line("M30 160 L30 175", "amber-500", 1.4),
    solid([rect(14, 140, 32, 6, 3), rect(14, 186, 32, 6, 3)], "jade-700", 5),
  ]);
  p.set("fx", [zed(150, 40, 1), zed(166, 24, 0.75), zed(180, 12, 0.55), drop(44, 72, 0.6)]);
  return p;
});

mood("stuffed", "Verdict MLE (quá bộ nhớ)", "Trang nộp bài", "Naomi bụng phồng, má phồng", () => {
  const p = new Pose().eyes("squeeze").set("mouth", mouth("pressed"));
  p.set("head", headFront({ extra: [circle(52, 98, 14), circle(148, 98, 14)], cheeks: true }));
  p.set("body", bodyFront({ d: "M68 118 C42 140 46 184 100 184 C154 184 158 140 132 118 Z", belly: [100, 160, 30, 21], spots: [[66, 140, 3], [134, 146, 3.4], [126, 128, 2.2]] }));
  p.set("feet", feetFront({ right: [76, 179], left: [124, 179] }));
  p.arms({ d: "M70 128 C60 138 64 152 76 158", wrist: [76, 158], dir: 20 });
  p.set("fx", [part("puff", line("M30 150 L40 152 M32 162 L42 160 M34 140 L42 144", "rose-500", 3)), part("puff", line("M170 150 L160 152 M168 162 L158 160 M166 140 L158 144", "rose-500", 3))]);
  return p;
});

mood("dizzy", "Verdict RE (lỗi khi chạy)", "Trang nộp bài", "Naomi choáng, mắt xoáy, sao quay quanh đầu", () => {
  const p = new Pose().eyes("spiral", {}, "spiral", { turns: 2.2 }).set("mouth", mouth("blep"));
  p.headT = "rotate(9 100 122)";
  p.naomi = "translate(0 -4) rotate(-3 100 190)";
  p.arm("right", { d: "M74 128 C62 136 54 140 46 140", wrist: [46, 140], dir: 160 });
  p.arm("left", { d: "M74 128 C68 142 66 152 68 160", wrist: [68, 160], dir: 80 });
  p.set("props-head", [
    el("ellipse", { cx: 100, cy: 34, rx: 46, ry: 9, fill: "none", stroke: C(INK), "stroke-width": 1.8, "stroke-dasharray": "3 5" }),
    part("star", star(58, 32, 8, "violet-500")),
    part("star", star(128, 25, 6.5, "violet-500")),
    part("star", star(146, 40, 5, "violet-200")),
  ]);
  return p;
});

mood("tangled", "Verdict CE (lỗi cú pháp)", "Trang nộp bài", "Naomi rối trong sợi dây, kính mờ", () => {
  const p = new Pose().set("mouth", mouth("wavy"));
  p.arms({ d: "M74 128 C68 140 70 150 76 156", wrist: [76, 156], dir: 40 }, "back");
  const lens = (cx) => [
    el("circle", { cx, cy: 66, r: 18, fill: C("slate-50"), stroke: C(INK), "stroke-width": 3.5 }),
    line(`M${cx - 10} ${62} C${cx - 4} ${56} ${cx + 2} ${66} ${cx + 9} ${60} M${cx - 9} ${72} C${cx - 3} ${67} ${cx + 3} ${76} ${cx + 10} ${70}`, "slate-300", 2.4),
  ];
  p.set("props-head", [line("M80 64 Q100 56 120 64", INK, 3.5), ...lens(62), ...lens(138)]);
  p.set("props", [
    g("cord", limb("M58 132 C80 120 120 154 142 136 C150 128 140 118 128 126 C110 140 70 150 64 166 C60 178 92 182 110 168 C126 156 150 160 150 176", 4, "blue-500", "round", 6)),
    g("plug", solid([rect(146, 176, 10, 12, 2)], "slate-300", 5)),
  ]);
  p.set("fx", [part("squiggle", line("M150 30 C156 22 164 34 170 26 C176 18 182 30 188 22", "blue-500", 3)), drop(170, 74, 0.8)]);
  return p;
});

mood("sorry", "Verdict SE / lỗi hệ thống / trang 500", "Trang nộp bài, error.tsx", "Naomi cầm biển đang sửa, xin lỗi", () => {
  const p = new Pose().eyes("open", { look: [0, 1], lid: { h: -6, a: -16 } }).set("mouth", mouth("awkward"));
  p.headT = "rotate(-5 100 122) translate(0 3)";
  // The sign stands left of centre so the tail still shows beside it.
  const stripes = [0, 1, 2, 3, 4, 5, 6].map((i) => `M${44 + i * 12} 147 L${50 + i * 12} 138`).join(" ");
  p.set("props", [
    g("sign", solid([rect(30, 132, 104, 52, 7)], WHITE, 7)),
    g("sign-band", [el("rect", { x: 36, y: 137.5, width: 92, height: 10, rx: 2, fill: C("slate-700") }), line(stripes, WHITE, 3.6, { "stroke-linecap": "butt" })]),
    g("wrench", [line("M72 174 L90 158", "slate-700", 6), el("circle", { cx: 93, cy: 155, r: 7, fill: C("slate-700") }), el("circle", { cx: 96, cy: 152, r: 3.2, fill: C(WHITE) })]),
  ]);
  p.arm("right", { d: "M74 128 C60 130 46 134 38 138", wrist: [38, 138], dir: 90 });
  p.arm("left", { mirror: false, d: "M126 128 C132 132 130 136 126 139", wrist: [126, 139], dir: 90 });
  p.set("fx", [drop(160, 60)]);
  return p;
});

mood("party", "Quiz 100 %", "Kết quả quiz", "Naomi đội mũ tiệc, pháo giấy", () => {
  const p = new Pose().eyes("star").set("mouth", mouth("grin"));
  p.naomi = "translate(0 -4)";
  p.shadow = { cx: 100, cy: 194, rx: 34, ry: 4 };
  p.set("head", headFront({ cheeks: true }));
  p.arms({ d: "M74 126 C56 124 44 110 40 94", wrist: [40, 94], dir: -105 });
  p.set("props-head", g("party-hat", [
    ...solid([shape("M70 46 L86 14 L106 40 Z")], "turmeric-300", 6),
    line("M77 32 L95 26 M73 41 L102 33", "jade-500", 3),
    ...solid([circle(86, 14, 4.5)], "jade-500", 5),
  ]));
  const bits = [[16, 30, "jade-300", 0], [40, 14, "rose-500", 30], [150, 12, "blue-500", -20], [178, 40, "turmeric-400", 15], [182, 88, "violet-500", 40], [18, 96, "turmeric-400", -30], [160, 70, "jade-300", 60], [132, 18, "turmeric-300", 10]];
  p.scene = bits.map(([x, y, c, r]) => part("confetti", el("rect", { x: x - 3.5, y: y - 2, width: 7, height: 4, rx: 1, transform: `rotate(${r} ${x} ${y})`, fill: C(c), stroke: C(INK), "stroke-width": 1.4 })));
  return p;
});

mood("proud", "Quiz ≥ 80 %", "Kết quả quiz", "Naomi chống nạnh, ngẩng đầu tự hào", () => {
  const p = new Pose().eyes("closed").set("mouth", mouth("smug"));
  p.headT = "rotate(-4 100 122) translate(0 -2)";
  p.set("head", headFront({ cheeks: true }));
  p.arms({ d: "M74 128 C50 128 48 150 64 156", wrist: [64, 156], dir: 40 });
  p.set("fx", [sparkle(162, 30, 0.9, "green-500"), sparkle(178, 50, 0.55, "green-500")]);
  return p;
});

mood("cheer", "Quiz 50–79 %", "Kết quả quiz", "Naomi giơ nắm tay cổ vũ", () => {
  const p = new Pose().eyes("open", { look: [2, -1], sparkle: true }).set("mouth", mouth("open"));
  p.arm("left", { d: "M74 128 C54 128 40 118 34 104", wrist: [34, 104], hand: "fist", dir: -90 });
  p.set("fx", [part("whoosh", line("M160 80 L156 70 M174 76 L178 66 M186 90 L195 86", "blue-500", 3))]);
  return p;
});

mood("comfort", "Quiz < 50 %", "Kết quả quiz", "Naomi ôm trái tim, an ủi", () => {
  const p = new Pose().eyes("happy").set("mouth", mouth("small"));
  p.headT = "rotate(-8 100 122)";
  p.set("head", headFront({ cheeks: true }));
  p.set("props", g("heart", el("path", { d: heartPath, transform: "translate(100 148) scale(2.1)", fill: C("violet-500"), stroke: C(INK), "stroke-width": 1.6, "stroke-linejoin": "round" })));
  p.arms({ d: "M74 128 C64 140 66 160 78 166", wrist: [78, 166], dir: -30 });
  return p;
});

mood("startled", "Quiz hết giờ", "Kết quả quiz", "Naomi giật mình nhìn đồng hồ báo thức", () => {
  const p = new Pose().eyes("wide", { look: [-3, 2] }).set("mouth", mouth("bigO"));
  p.naomi = "translate(2 -10)";
  p.shadow = { cx: 102, cy: 194, rx: 32, ry: 4 };
  p.arms({ d: "M74 126 C56 122 44 110 38 98", wrist: [38, 98], dir: -125, spread: 1.25 });
  p.scene = g("alarm-clock", [
    ...solid([circle(20, 150, 6), circle(42, 150, 6)], "amber-500", 5),
    ...solid([circle(31, 168, 17)], "amber-500", 5),
    el("circle", { cx: 31, cy: 168, r: 12, fill: C(WHITE) }),
    line("M31 168 L31 159 M31 168 L37 171", INK, 2.5),
    line("M22 184 L18 190 M40 184 L44 190", INK, 3),
    motion("M8 156 C4 162 4 170 8 176 M54 156 C58 162 58 170 54 176"),
  ]);
  p.set("fx", part("bang", [line("M100 18 L100 30", "amber-600", 4.5), el("circle", { cx: 100, cy: 38, r: 2.6, fill: C("amber-600") }), line("M114 20 L111 31", "amber-600", 4), el("circle", { cx: 109.5, cy: 38, r: 2.3, fill: C("amber-600") })]));
  return p;
});

mood("fire", "Chuỗi ngày học còn giữ", "Khối thành tích /khoa-hoc-cua-toi", "Naomi giơ ngọn đuốc chuỗi ngày", () => {
  const p = new Pose().eyes("open", { look: [3, -3], sparkle: true, lid: { h: -9, a: 12 } }).set("mouth", mouth("grin"));
  const flame = [
    el("path", { d: "M164 64 C150 56 152 40 160 28 C162 38 168 38 170 30 C180 42 180 58 164 64 Z", fill: C("orange-500"), stroke: C(INK), "stroke-width": 2.6, "stroke-linejoin": "round" }),
    el("path", { d: "M164 60 C158 56 158 48 162 42 C164 48 168 48 168 44 C172 50 170 58 164 60 Z", fill: C("orange-200") }),
  ];
  p.arm("left", {
    mirror: false,
    d: "M126 128 C150 126 166 112 170 96",
    wrist: [170, 96],
    dir: -80,
    held: [...limb("M166 114 L178 66", 5, "slate-500", "round", 6), ...solid([shape("M170 66 L186 66 L184 74 L172 74 Z")], "slate-300", 5), part("flame", el("g", { transform: "translate(14 2)" }, flame))],
  });
  p.arm("right", { d: "M74 128 C64 138 62 148 64 154", wrist: [64, 154], hand: "fist", dir: 90 });
  return p;
});

mood("sad", "Chuỗi ngày vừa mất", "Khối thành tích /khoa-hoc-cua-toi", "Naomi buồn nhìn ngọn nến vừa tắt, vẫn còn đốm lửa", () => {
  const p = new Pose().eyes("open", { look: [-4, 3], lid: { h: -5, a: -18 } }).set("mouth", mouth("frown"));
  p.naomi = "translate(14 15.5) scale(0.92)";
  p.shadow = { cx: 110, cy: 194, rx: 38, ry: 4.5 };
  p.headT = "rotate(-7 100 122) translate(0 2)";
  p.scene = g("candle", [
    ...solid([ellipse(24, 186, 16, 5)], "slate-300", 5),
    ...solid([rect(17, 156, 14, 28, 3)], WHITE, 5),
    line("M24 156 L24 150", INK, 2),
    el("circle", { cx: 24, cy: 149, r: 2.4, fill: C("orange-500") }),
    part("smoke", line("M24 144 C18 136 30 128 24 118 C20 110 26 104 24 96", "slate-300", 2.6)),
  ]);
  p.set("fx", [drop(66, 88, 0.7)]);
  return p;
});

mood("levelup", "Lên hạng trên bảng xếp hạng", "/bang-xep-hang", "Naomi nhảy lên bục", () => {
  const p = new Pose().eyes("happy").set("mouth", mouth("grin"));
  p.set("head", headFront({ cheeks: true }));
  p.naomi = "translate(22 -10) scale(0.78)";
  p.shadow = { cx: 100, cy: 156, rx: 26, ry: 3.4 };
  p.arms({ d: "M74 126 C56 124 44 110 40 94", wrist: [40, 94], dir: -105 });
  p.scene = g("podium", [
    ...solid([rect(52, 152, 96, 42, 6)], "jade-100", 7),
    ...solid([shape("M100 160 L114 176 L106 176 L106 186 L94 186 L94 176 L86 176 Z")], "jade-500", 4),
    sparkle(30, 40), sparkle(176, 30, 0.8), sparkle(172, 112, 0.6),
    motion("M66 146 L62 138 M134 146 L138 138"),
  ]);
  return p;
});

mood("graduate", "Nhận chứng chỉ", "Trang học khi hoàn thành, /cert/[code]", "Naomi đội mũ tốt nghiệp, cầm bằng", () => {
  const p = new Pose().eyes("happy").set("mouth", mouth("small"));
  p.set("head", headFront({ cheeks: true }));
  p.set("props-head", named("g", "mortarboard", { transform: "translate(-12 -10) rotate(-14 100 40)" }, [
    ...solid([shape("M76 52 C78 42 122 42 124 52 L124 58 C110 62 90 62 76 58 Z")], INK, 4),
    ...solid([shape("M54 40 L100 24 L146 40 L100 56 Z")], "jade-800", 4),
    el("circle", { cx: 100, cy: 40, r: 3, fill: C("turmeric-400"), stroke: C(INK), "stroke-width": 1.5 }),
    line("M100 40 L140 46 L141 64", "turmeric-400", 2.6),
    el("rect", { x: 137.5, y: 63, width: 7, height: 11, rx: 2, fill: C("turmeric-400"), stroke: C(INK), "stroke-width": 1.8 }),
  ]));
  p.arm("right", {
    d: "M74 128 C58 134 48 132 42 126",
    wrist: [42, 126],
    dir: -150,
    held: [...solid([rect(14, 116, 40, 14, 7, [-35, 34, 123])], WHITE, 5), el("rect", { x: 31, y: 115.5, width: 6, height: 15, transform: "rotate(-35 34 123)", fill: C("jade-600") })],
  });
  p.scene = [sparkle(170, 100, 0.8), sparkle(30, 168, 0.6)];
  return p;
});

mood("lost", "Trang 404", "app/not-found.tsx + 404 khóa học, chứng chỉ", "Naomi cầm bản đồ ngược, lạc đường", () => {
  const p = new Pose()
    .eyes("open", { look: [2, 5] }, "open", { look: [-2, 5], lid: { h: -4, a: 0 } })
    .set("mouth", mouth("o"));
  p.set("props", g("map", [
    ...solid([shape("M58 124 L86 129 L114 124 L142 129 L142 172 L114 167 L86 172 L58 167 Z")], WHITE, 7),
    line("M86 129 L86 172 M114 124 L114 167", "slate-300", 2),
    line("M70 160 C80 150 90 160 100 150 C108 142 116 150 124 142", "jade-500", 3, { "stroke-dasharray": "4 4" }),
    line("M124 132 L132 140 M132 132 L124 140", "red-500", 3),
    g("compass", [line("M72 133 L72 147 M67 142 L72 147 L77 142", INK, 2.2), line("M69 157 L69 151 L75 157 L75 151", INK, 1.8)]),
  ]));
  p.arms({ d: "M74 128 C68 134 62 138 58 142", wrist: [58, 142], dir: 100 });
  p.set("fx", g("question", [line("M156 16 C156 6 174 6 174 16 C174 24 165 25 165 33", SPOT, 6), el("circle", { cx: 165, cy: 43, r: 3.4, fill: C(SPOT) })]));
  return p;
});

// Empty states: one waiting pose; the prop says which list is empty. Props are
// functions so each output (image or web) draws them with its own colours.
function emptyPose() {
  const p = new Pose().eyes("open", { look: [-3, 2] }).set("mouth", mouth("small"));
  p.naomi = "translate(16 19.4) scale(0.9)";
  p.shadow = { cx: 104, cy: 194, rx: 36, ry: 4 };
  p.headT = "rotate(-6 100 122)";
  p.arm("right", { d: "M74 128 C64 132 54 136 46 136", wrist: [46, 136], dir: 125 });
  return p;
}
const EMPTY_PROPS = {
  cart: ["Giỏ hàng trống", "Naomi cạnh giỏ hàng trống", () => [
    line("M6 134 L14 134 L20 146", INK, 3.4),
    el("path", { d: "M18 146 L62 146 L56 172 L24 172 Z", fill: C(WHITE), stroke: C(INK), "stroke-width": 3.4, "stroke-linejoin": "round" }),
    line("M32 150 L34 168 M46 150 L44 168 M21 158 L59 158", "slate-300", 2),
    ...solid([circle(28, 184, 4.5), circle(52, 184, 4.5)], "slate-500", 5),
    line("M24 172 L22 178 L58 178", INK, 3.4),
  ]],
  courses: ["Chưa có khóa học", "Naomi cạnh cuốn sách đóng", () => [
    ...solid([rect(18, 132, 40, 52, 4)], "jade-600", 6),
    el("rect", { x: 22, y: 136, width: 32, height: 44, rx: 2, fill: "none", stroke: C("jade-300"), "stroke-width": 2 }),
    line("M32 152 L27 158 L32 164 M44 152 L49 158 L44 164", WHITE, 2.6),
    el("path", { d: "M46 132 L46 146 L50 142 L54 146 L54 132 Z", fill: C("jade-300"), stroke: C(INK), "stroke-width": 1.6, "stroke-linejoin": "round" }),
  ]],
  notifications: ["Chưa có thông báo", "Naomi cạnh cái chuông đang ngủ", () => [
    ...solid([shape("M20 172 C24 166 22 150 26 142 C30 132 50 132 54 142 C58 150 56 166 60 172 Z")], WHITE, 6),
    ...solid([circle(40, 178, 5)], "slate-300", 5),
    ...solid([circle(40, 130, 3.4)], "slate-300", 4),
    zed(8, 122, 0.8), zed(18, 108, 0.6),
  ]],
  notes: ["Chưa có ghi chú", "Naomi cạnh sổ ghi chú trống và cây bút", () => [
    ...solid([rect(14, 134, 42, 52, 4)], WHITE, 6),
    line("M22 150 L48 150 M22 160 L48 160 M22 170 L40 170", "slate-300", 2),
    line("M20 134 L20 128 M30 134 L30 128 M40 134 L40 128 M50 134 L50 128", INK, 2.6),
    g("pencil", [...limb("M56 186 L64 146", 5, "jade-300", "butt", 5), el("path", { d: "M53.5 186.5 L58.5 187.5 L55 194 Z", fill: C(INK) })]),
  ]],
  search: ["Tìm không ra", "Naomi cạnh cái kính lúp không thấy gì", () => [
    ...limb("M46 168 L60 186", 6, "slate-500", "round", 6),
    el("circle", { cx: 34, cy: 152, r: 17, fill: C("slate-50"), stroke: C(INK), "stroke-width": 4.5 }),
    line("M26 144 C30 140 36 140 40 142", WHITE, 3),
  ]],
};
mood("empty", "Danh sách trống (đạo cụ theo chỗ)", "Mọi empty state", "Naomi ngồi chờ", () => emptyPose());
for (const [key, [event, label, prop]] of Object.entries(EMPTY_PROPS)) {
  mood(`empty-${key}`, event, "Empty state", label, () => {
    const p = emptyPose();
    p.scene = g(`prop-${key}`, prop());
    return p;
  });
}

mood("thinking", "Trợ giảng AI đang trả lời (stream)", "Tab “Trợ giảng AI”", "Naomi chống cằm suy nghĩ", () => {
  const p = new Pose().eyes("open", { look: [3, -4], lid: { h: -7, a: 6 } }).set("mouth", mouth("side"));
  p.headT = "rotate(5 100 122)";
  p.arm("right", { d: "M74 128 C60 136 66 124 76 114", wrist: [76, 114], dir: -40 }, "front");
  p.set("fx", g("thought", [
    part("bubble", solid([circle(150, 40, 3.2)], WHITE, 4)),
    part("bubble", solid([circle(160, 28, 4.6)], WHITE, 4)),
    part("bubble", [...solid([ellipse(178, 14, 16, 11)], WHITE, 5), dots([[171, 14, 2.2], [178, 14, 2.2], [185, 14, 2.2]], "jade-600")]),
  ]));
  return p;
});

mood("answer", "Trợ giảng AI trả lời có nguồn", "Tab “Trợ giảng AI”", "Naomi cầm cuốn sách mở", () => {
  const p = new Pose().eyes("open", { look: [1, 0], sparkle: true }).set("mouth", mouth("open"));
  p.set("props", g("book", [
    ...solid([shape("M100 142 C86 134 66 134 52 140 L54 178 C68 172 86 172 100 180 C114 172 132 172 146 178 L148 140 C134 134 114 134 100 142 Z")], "jade-600", 6),
    el("path", { d: "M100 140 C88 132 70 132 58 136 L60 170 C72 166 88 166 100 174 Z", fill: C(WHITE), stroke: C(INK), "stroke-width": 2.4, "stroke-linejoin": "round" }),
    el("path", { d: "M100 140 C112 132 130 132 142 136 L140 170 C128 166 112 166 100 174 Z", fill: C(WHITE), stroke: C(INK), "stroke-width": 2.4, "stroke-linejoin": "round" }),
    line("M66 146 C76 143 86 144 94 148 M66 154 C76 151 86 152 94 156 M106 148 C114 144 124 143 134 146 M106 156 C114 152 124 151 134 154", "slate-300", 2),
    el("path", { d: "M118 172 L118 186 L122 182 L126 186 L126 171 Z", fill: C("jade-300"), stroke: C(INK), "stroke-width": 1.6, "stroke-linejoin": "round" }),
  ]));
  p.arms({ d: "M74 128 C64 136 58 144 56 152", wrist: [56, 152], dir: 40 });
  p.set("fx", [sparkle(30, 44, 0.8, "jade-300"), sparkle(174, 52, 0.6, "jade-300")]);
  return p;
});

mood("wave", "Đăng ký xong, chào trở lại", "Onboarding, trang chủ khi đăng nhập", "Naomi vẫy tay chào", () => {
  const p = new Pose().eyes("open", { look: [1, 0], sparkle: true }).set("mouth", mouth("open"));
  p.headT = "rotate(-6 100 122)";
  p.set("head", headFront({ cheeks: true }));
  p.arm("left", { d: "M74 128 C52 120 34 100 28 76", wrist: [28, 76], dir: -100, spread: 1.3 });
  p.set("fx", [motion("M160 50 C164 42 172 38 180 38"), motion("M192 58 C196 66 196 76 192 84")]);
  return p;
});

mood("paid", "Thanh toán thành công", "/thanh-toan/ket-qua", "Naomi giơ túi hàng có dấu tích", () => {
  const p = new Pose().eyes("happy").set("mouth", mouth("grin"));
  p.naomi = "translate(0 -6)";
  p.shadow = { cx: 100, cy: 194, rx: 34, ry: 4 };
  p.set("head", headFront({ cheeks: true }));
  // The bag hangs on her right, the side without the tail.
  p.arm("right", {
    d: "M74 126 C56 126 42 114 36 100",
    wrist: [36, 100],
    dir: -95,
    held: [line("M16 104 C16 84 34 84 34 104", INK, 3.4), ...solid([shape("M8 102 L42 102 L45 138 L5 138 Z")], "jade-100", 6), part("tick", line("M15 120 L22 127 L35 112", "green-600", 4))],
  });
  p.arm("left", { d: "M74 126 C56 126 42 118 36 104", wrist: [36, 104], dir: -115 });
  p.scene = [sparkle(178, 58, 0.8, "jade-300"), sparkle(60, 22, 0.6, "jade-300")];
  return p;
});

mood("oops", "Thanh toán thất bại", "/thanh-toan/ket-qua", "Naomi ngơ ngác cầm thẻ, dấu X đỏ", () => {
  const p = new Pose().eyes("dot", { look: [0, 1] }).set("mouth", mouth("o"));
  p.headT = "rotate(7 100 122)";
  p.arm("left", {
    mirror: false,
    d: "M126 128 C132 140 128 148 120 152",
    wrist: [120, 152],
    dir: 180,
    held: [...solid([rect(84, 134, 44, 28, 4, [-10, 106, 148])], WHITE, 5), el("rect", { x: 84, y: 140, width: 44, height: 6, transform: "rotate(-10 106 148)", fill: C("jade-600") }), el("rect", { x: 89, y: 150, width: 9, height: 7, rx: 1.5, transform: "rotate(-10 106 148)", fill: C("slate-300") })],
  });
  p.set("fx", [
    part("cross", [...solid([circle(140, 124, 9)], "red-500", 4), line("M136 120 L144 128 M144 120 L136 128", WHITE, 2.8)]),
    drop(36, 58),
  ]);
  return p;
});

// ---------------------------------------------------------------- the three views
function viewFront() {
  return new Pose().eyes("open", { look: [0, 1] });
}

function viewThreeQuarter() {
  // Turned about 30° towards the viewer's left: her left side comes forward.
  const p = new Pose();
  p.set("tail", tail({ transform: "translate(4 0)" }));
  p.set("feet", [
    foot("foot-right", [72, 178], "right", { sole: [12, 7], toeR: 4.5, toes: [[-13, 3], [-6, 8], [4, 8]] }),
    foot("foot-left", [112, 179], "left", { toes: [[12, 8], [1, 10], [-10, 7]] }),
  ]);
  p.set("body", bodyFront({ d: "M70 120 C58 150 62 178 96 179 C130 178 138 150 128 120 Z", belly: [86, 158, 15, 17], spots: [[106, 134, 2.8], [110, 148, 2.4], [104, 163, 2], [92, 130, 2]] }));
  p.arm("right", { d: "M74 128 C68 140 62 148 58 155", wrist: [58, 155], dir: 115, w: 7 });
  p.arm("left", { mirror: false, d: "M122 128 C127 140 127 150 123 158", wrist: [123, 158], dir: 92 });
  p.set("head", [
    g("head-shape", solid([ellipse(98, 83, 57, 40), ellipse(60, 68, 16, 20), circle(128, 64, 21)], SKIN)),
    g("head-spots", dots([[110, 50, 4.4], [97, 56, 2.6], [122, 55, 3], [108, 63, 2], [148, 92, 3], [140, 106, 2.2]])),
    g("nostrils", dots([[62, 86, 1.4], [73, 85, 1.6]], INK)),
  ]);
  p.L.eyes = [
    g("eye-right", [
      el("ellipse", { cx: 58, cy: 68, rx: 11, ry: 15, fill: C(WHITE), stroke: C(INK), "stroke-width": 3 }),
      el("ellipse", { cx: 55.5, cy: 69, rx: 7.6, ry: 11, fill: C(IRIS) }),
      el("ellipse", { cx: 55, cy: 69, rx: 3.6, ry: 8.5, fill: C(INK) }),
      el("circle", { cx: 58, cy: 63, r: 2.6, fill: C(WHITE) }),
    ]),
    g("eye-left", [
      el("circle", { cx: 128, cy: 64, r: 15.5, fill: C(WHITE), stroke: C(INK), "stroke-width": 3 }),
      el("circle", { cx: 124, cy: 66, r: 11, fill: C(IRIS) }),
      el("ellipse", { cx: 123, cy: 66, rx: 5.2, ry: 8.5, fill: C(INK) }),
      el("circle", { cx: 127, cy: 60, r: 3.2, fill: C(WHITE) }),
    ]),
  ];
  p.L.eyelids = [];
  p.set("mouth", line("M50 98 C62 109 92 111 108 101", INK, 4));
  return p;
}

function viewSide() {
  // Profile, facing the viewer's left: her left side is towards us. The head
  // sits 3 lower so the eye stays on the eye line of the other two views.
  const p = new Pose();
  p.headT = "translate(0 3)";
  p.shadow = { cx: 108, cy: 194, rx: 44, ry: 4.5 };
  p.set("tail", tail({ transform: "translate(6 2) scale(0.96)" }));
  p.set("feet", [
    foot("foot-right", [80, 180], "right", { sole: [12, 6.5], toeR: 4.5, toes: [[-12, 3], [-5, 7]] }),
    foot("foot-left", [100, 180], "right", { sole: [15, 7.5], toes: [[-15, 3], [-8, 8], [1, 9]] }),
  ]);
  p.set("body", [
    solid([shape("M82 118 C68 148 72 178 104 179 C134 178 138 148 124 118 Z")], SKIN),
    named("path", "belly", { d: "M82 136 C72 150 72 168 84 176 C92 168 94 148 88 136 Z", fill: C(BELLY) }),
    g("body-spots", dots([[124, 136, 3], [128, 152, 2.6], [120, 166, 2.2], [114, 126, 2]])),
  ]);
  p.arm("right", { d: "M92 128 C86 140 80 148 74 154", wrist: [74, 154], dir: 140 }, "behind");
  p.arm("left", { mirror: false, d: "M114 126 C114 140 112 150 107 158", wrist: [107, 158], dir: 100 });
  p.set("head", [
    g("head-shape", solid([ellipse(106, 80, 46, 38), ellipse(70, 90, 30, 24), circle(104, 62, 20)], SKIN)),
    g("head-spots", dots([[128, 58, 3.6], [140, 74, 2.6], [134, 92, 3], [120, 46, 2.4], [146, 90, 2]])),
    g("nostrils", dots([[46, 84, 1.7]], INK)),
  ]);
  p.L.eyes = [
    g("eye-left", [
      el("circle", { cx: 104, cy: 62, r: 15, fill: C(WHITE), stroke: C(INK), "stroke-width": 3 }),
      el("circle", { cx: 99, cy: 63, r: 10.5, fill: C(IRIS) }),
      el("ellipse", { cx: 98, cy: 63, rx: 5, ry: 8.2, fill: C(INK) }),
      el("circle", { cx: 102, cy: 57, r: 3, fill: C(WHITE) }),
    ]),
  ];
  p.L.eyelids = [];
  p.set("mouth", line("M44 96 C58 102 80 104 94 97", INK, 4));
  return p;
}

const VIEWS = [
  { name: "front", label: "Naomi nhìn thẳng", build: viewFront },
  { name: "three-quarter", label: "Naomi nhìn ba phần tư", build: viewThreeQuarter },
  { name: "side", label: "Naomi nhìn nghiêng", build: viewSide },
];

// ---------------------------------------------------------------- write
function clean(dir) {
  fs.mkdirSync(dir, { recursive: true });
  for (const f of fs.readdirSync(dir)) if (f.endsWith(".svg")) fs.unlinkSync(path.join(dir, f));
}
const out = { views: path.join(HERE, "views"), moods: path.join(HERE, "moods"), layers: path.join(HERE, "layers") };
Object.values(out).forEach(clean);

const manifest = { note: "Generated by build.cjs. Mood list = section 5 of docs/ui-ux/thiet-ke-nang-cap-ui-ux.md plus rest.", views: [], moods: [], layers: [] };
for (const v of VIEWS) {
  const file = `naomi-${v.name}.svg`;
  fs.writeFileSync(path.join(out.views, file), v.build().render(v.label, v.name));
  manifest.views.push({ view: v.name, file: `views/${file}`, label: v.label });
}
for (const m of MOODS) {
  const file = `naomi-${m.name}.svg`;
  fs.writeFileSync(path.join(out.moods, file), m.build().render(m.label, m.name));
  manifest.moods.push({ mood: m.name, event: m.event, where: m.where, label: m.label, file: `moods/${file}` });
}
// The three views side by side on proportion guides, for the model sheet.
// Guides: top of the head (eye bumps), eye line, chin, ground.
const GUIDES = { "head-top": 37.5, eyes: 66, chin: 126.5, ground: 199.5 };
const turnaround = [
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 210" role="img" aria-label="Naomi nhìn thẳng, ba phần tư và nghiêng, trên các đường gióng tỉ lệ">`,
  `  <!-- Generated by docs/ui-ux/mascot/naomi/build.cjs. Edit the script, not this file. -->`,
  `  ${el("g", { id: "guides", fill: "none", stroke: C("slate-300"), "stroke-width": 1, "stroke-dasharray": "4 4" }, Object.values(GUIDES).map((y) => el("path", { d: `M0 ${y} L640 ${y}` })))}`,
  ...VIEWS.map((v, i) => {
    const inner = v.build().render(v.label, v.name).replace(/^[\s\S]*?<!--[^>]*-->\n/, "").replace(/<\/svg>\s*$/, "").replace(/ id="[^"]*"/g, "");
    return `  <g data-view="${v.name}" transform="translate(${i * 220} 0)">\n${inner}  </g>`;
  }),
  `</svg>`,
  "",
].join("\n");
fs.mkdirSync(path.join(HERE, "sheet"), { recursive: true });
fs.writeFileSync(path.join(HERE, "sheet", "naomi-turnaround.svg"), turnaround);
manifest.sheet = { file: "sheet/naomi-turnaround.svg", guides: GUIDES };

// The layers of one mood, each alone, for the model sheet's exploded view.
const EXPLODE = "partial";
const exploded = MOODS.find((m) => m.name === EXPLODE).build();
for (const n of ["shadow", "scene", ...exploded.order()]) {
  const svg = exploded.render(`Lớp ${n} của ${EXPLODE}`, EXPLODE, n);
  if (!/<(path|circle|ellipse|rect)/.test(svg)) continue;
  const file = `naomi-${EXPLODE}-${n}.svg`;
  fs.writeFileSync(path.join(out.layers, file), svg);
  manifest.layers.push({ layer: n, file: `layers/${file}` });
}
fs.writeFileSync(path.join(HERE, "naomi.json"), JSON.stringify(manifest, null, 2) + "\n");

// ---------------------------------------------------------------- web drawings
// frontend/components/mascot/art/<mood>.ts: one module per mood, so a page
// downloads only the moods it shows. frontend/lib/mascot/moods.ts: the mood
// list, labels, pivots and the palette the drawings read.
WEB = true;
const FRONTEND = path.join(REPO, "frontend");
const ART = path.join(FRONTEND, "components", "mascot", "art");
const HEADER = "// Generated by docs/ui-ux/mascot/naomi/build.cjs. Edit the script, not this file.\n";
fs.mkdirSync(ART, { recursive: true });
for (const f of fs.readdirSync(ART)) if (f.endsWith(".ts")) fs.unlinkSync(path.join(ART, f));
// `index` and `server` are the two loaders; a mood by either name would clash.
for (const m of MOODS) if (m.name === "index" || m.name === "server") throw new Error(`mood name ${m.name} is taken by a loader file`);
const meta = [];
for (const m of MOODS) {
  const pose = m.build();
  const svg = pose.renderWeb(m.name);
  if (/['\\\n]/.test(svg)) throw new Error(`${m.name}: the web drawing must fit in a single-quoted line`);
  if (/ id="/.test(svg) || /data-layer="[^"]*" transform=/.test(svg)) throw new Error(`${m.name}: a named layer kept an id or a transform`);
  fs.writeFileSync(path.join(ART, `${m.name}.ts`), `${HEADER}const svg = '${svg}';\n\nexport default svg;\n`);
  meta.push({ mood: m.name, label: m.label, ...pose.anchors() });
}
const q = JSON.stringify;
fs.writeFileSync(
  path.join(ART, "index.ts"),
  [
    HEADER,
    "/** One chunk per mood: `import()` with a literal path, so the bundler splits them. */",
    "export const ART = {",
    ...MOODS.map((m) => `  ${q(m.name)}: () => import(${q(`./${m.name}`)}),`),
    "} as const;",
    "",
  ].join("\n")
);
const ident = (name) => name.replace(/-(\w)/g, (_, c) => c.toUpperCase());
fs.writeFileSync(
  path.join(ART, "server.ts"),
  [
    HEADER,
    "// Every drawing, synchronously: for server rendering only. The component",
    "// reaches this module behind `typeof window === \"undefined\"`, which Next",
    "// replaces at build time, so the browser bundle never contains it.",
    ...MOODS.map((m) => `import ${ident(m.name)} from ${q(`./${m.name}`)};`),
    "",
    "export const ART_SYNC = {",
    ...MOODS.map((m) => `  ${q(m.name)}: ${ident(m.name)},`),
    "} as const;",
    "",
  ].join("\n")
);
const palette =Object.fromEntries([...USED].sort().map((n) => [n, HEX[n]]));
fs.mkdirSync(path.join(FRONTEND, "lib", "mascot"), { recursive: true });
fs.writeFileSync(
  path.join(FRONTEND, "lib", "mascot", "moods.ts"),
  [
    HEADER,
    "export const MOODS = [",
    ...meta.map((m) => `  ${q(m.mood)},`),
    "] as const;",
    "",
    "export type Mood = (typeof MOODS)[number];",
    "",
    "export type MoodMeta = {",
    "  /** What the drawing shows, for a mascot that carries meaning (role=\"img\"). */",
    "  label: string;",
    "  /** Her feet in <svg> coordinates: the pivot for jumps and sways. */",
    "  ground: readonly [number, number];",
    "  /** Centre of the shadow under her feet, in <svg> coordinates. */",
    "  shadow: readonly [number, number] | null;",
    "};",
    "",
    "export const MOOD_META: Record<Mood, MoodMeta> = {",
    ...meta.map((m) => `  ${q(m.mood)}: { label: ${q(m.label)}, ground: [${m.ground.join(", ")}], shadow: ${m.shadow ? `[${m.shadow.join(", ")}]` : "null"} },`),
    "};",
    "",
    "/** Design-system colours the drawings read as `var(--color-<name>)`, with their values in tokens.json. */",
    "export const PALETTE: Record<string, string> = {",
    ...Object.entries(palette).map(([n, v]) => `  ${q(n)}: ${q(v)},`),
    "};",
    "",
  ].join("\n")
);
WEB = false;

console.log(`${manifest.views.length} views, ${manifest.moods.length} moods, ${manifest.layers.length} layers of ${EXPLODE}; ${meta.length} web drawings, ${Object.keys(palette).length} colours`);
