// How Naomi moves for each mood: one reaction per event, then still.
//
// Data only (no DOM), so `npm test` can check every reaction against the
// drawings it moves (lib/mascot/mascot.test.ts). components/mascot/play.ts
// turns it into Web Animations.
//
// Coordinates are those of the drawing (viewBox 0 0 200 200), in the space of
// the piece that moves: parts of Naomi in her own drawing space, the whole
// character and her shadow in <svg> space (MOOD_META.ground / .shadow, which
// the generator works out from each pose).
import type { Mood, MoodMeta } from "./moods";

export type Ease = "standard" | "enter" | "exit" | "overshoot";

/** A pivot in drawing units, or a point of the piece's own box. */
export type Origin = readonly [number, number] | "center" | "base";

/** One animation of one or more named pieces (`data-layer` or `data-part`). */
export type Track = {
  target: readonly string[];
  origin: Origin;
  /** Start, in ms from the beginning of the reaction. */
  at: number;
  /** Extra delay per matched piece, in document order. */
  stagger?: number;
  duration: number;
  /** Keyframe offsets 0…1; evenly spaced when left out. */
  times?: readonly number[];
  /** Design-system curve per segment (or one for all). Default `standard`. */
  ease?: Ease | readonly Ease[];
  x?: readonly number[];
  y?: readonly number[];
  scale?: readonly number[];
  scaleX?: readonly number[];
  scaleY?: readonly number[];
  rotate?: readonly number[];
  opacity?: readonly number[];
};

/**
 * After the reaction. `hold`: she stays in the mood's own pose — the same
 * picture someone with reduced motion sees, and the one a reopened result
 * shows, so the end state never depends on having watched the animation.
 * `rest`: she cross-fades to the resting pose; only for a passing gesture
 * (`wave`), never for a mood whose props or framing would vanish with it
 * (the podium of `levelup`, the candle of `sad`, the cap of `graduate`).
 */
export type Settle = "rest" | "hold";

export type Reaction = { settle: Settle; tracks: readonly Track[] };

/** Upper bound of one reaction: token `duration-mascot`. */
export const REACTION_MAX_MS = 2400;
/** The cross-fade back to rest: token `duration-base`. */
export const SWAP_MS = 220;
/** Stillness between the end of a reaction and the cross-fade to rest. */
export const LINGER_MS = 400;

// Pivots inside Naomi's drawing (docs/ui-ux/mascot/naomi/build.cjs).
const NECK = [100, 122] as const;
const SHOULDER = { right: [74, 128], left: [126, 128] } as const;
const TAIL_BASE = [116, 166] as const;
const EYE = { right: [62, 66], left: [138, 66] } as const;
/** The head layers turn together. */
const HEAD = ["head", "eyes", "eyelids", "mouth", "props-head"] as const;

type At = { at?: number; duration?: number };
type Side = "right" | "left";

// ---------------------------------------------------------------- moves

/** Crouch, jump, land with a little overshoot; the shadow shrinks under her. */
function hop(meta: MoodMeta, { at = 0, duration = 1400, height = 30 }: At & { height?: number } = {}): Track[] {
  const k = height / 30;
  const times = [0, 0.15, 0.5, 0.78, 1];
  const ease: Ease[] = ["standard", "enter", "exit", "overshoot"];
  const tracks: Track[] = [
    {
      target: ["naomi"],
      origin: meta.ground,
      at,
      duration,
      times,
      ease,
      y: [0, 0, -height, 0, 0],
      scaleX: [1, 1 + 0.06 * k, 1 - 0.04 * k, 1 + 0.05 * k, 1],
      scaleY: [1, 1 - 0.08 * k, 1 + 0.06 * k, 1 - 0.06 * k, 1],
    },
  ];
  if (meta.shadow) {
    tracks.push({
      target: ["shadow"],
      origin: meta.shadow,
      at,
      duration,
      times,
      ease,
      scaleX: [1, 1.04, 1 - 0.4 * k, 1.06, 1],
      opacity: [1, 1, 1 - 0.45 * k, 1, 1],
    });
  }
  return tracks;
}

/** Up and down once, like a breath. */
function bob(meta: MoodMeta, { at = 0, duration = 800, height = 3 }: At & { height?: number } = {}): Track[] {
  return [{ target: ["naomi"], origin: meta.ground, at, duration, times: [0, 0.45, 1], y: [0, -height, 0] }];
}

/** The whole character leans (degrees, around her feet). */
function sway(meta: MoodMeta, rotate: number[], { at = 0, duration = 1600 }: At = {}): Track[] {
  return [{ target: ["naomi"], origin: meta.ground, at, duration, rotate }];
}

/** The whole character trembles sideways. */
function shake(meta: MoodMeta, x: number[], { at = 0, duration = 900 }: At = {}): Track[] {
  return [{ target: ["naomi"], origin: meta.ground, at, duration, x }];
}

/** The head turns around the neck (degrees). */
function tilt(rotate: number[], { at = 0, duration = 1200 }: At = {}): Track[] {
  return [{ target: HEAD, origin: NECK, at, duration, rotate }];
}

/** The head moves up (negative) or down. */
function nod(y: number[], { at = 0, duration = 1000 }: At = {}): Track[] {
  return [{ target: HEAD, origin: NECK, at, duration, y }];
}

/** Both eyes close and open. Only for moods whose eyes are open. */
function blink({ at = 0 }: At = {}): Track[] {
  return (["right", "left"] as const).map((side) => ({
    target: [`eye-${side}`, `lid-${side}`],
    origin: EYE[side],
    at,
    duration: 240,
    times: [0, 0.5, 1],
    scaleY: [1, 0.08, 1],
  }));
}

/** An arm swings around its shoulder (degrees). */
function swing(side: Side, rotate: number[], { at = 0, duration = 1200 }: At = {}): Track[] {
  return [{ target: [`arm-${side}`], origin: SHOULDER[side], at, duration, rotate }];
}

function wag(rotate: number[], { at = 0, duration = 1500 }: At = {}): Track[] {
  return [{ target: ["tail"], origin: TAIL_BASE, at, duration, rotate }];
}

/** Pieces appear by growing from small, one after another. */
function pop(target: string, { at = 0, duration = 520, stagger = 0, origin = "center" }: At & { stagger?: number; origin?: Origin } = {}): Track[] {
  return [{ target: [target], origin, at, duration, stagger, ease: "overshoot", scale: [0.2, 1], opacity: [0, 1] }];
}

/** Pieces drift into place from below (positive `from`) or above, fading in. */
function drift(target: string, { at = 0, duration = 800, stagger = 0, from = 10, turn = 0 }: At & { stagger?: number; from?: number; turn?: number } = {}): Track[] {
  return [
    {
      target: [target],
      origin: "center",
      at,
      duration,
      stagger,
      ease: "enter",
      y: [from, 0],
      opacity: [0, 1],
      ...(turn ? { rotate: [turn, 0] } : {}),
    },
  ];
}

/** Pieces turn on themselves once. */
function spin(target: string, { at = 0, duration = 1600, stagger = 0 }: At & { stagger?: number } = {}): Track[] {
  return [{ target: [target], origin: "center", at, duration, stagger, rotate: [0, 360] }];
}

/** A piece swells and settles. */
function pulse(target: string, scale: number[], { at = 0, duration = 1400, origin = "center" }: At & { origin?: Origin } = {}): Track[] {
  return [{ target: [target], origin, at, duration, scale }];
}

/** A piece rocks around a point (degrees). */
function rock(target: string, origin: Origin, rotate: number[], { at = 0, duration = 900 }: At = {}): Track[] {
  return [{ target: [target], origin, at, duration, rotate }];
}

// ---------------------------------------------------------------- moods

const REACTIONS: Record<Mood, (meta: MoodMeta) => Reaction> = {
  rest: (m) => ({ settle: "hold", tracks: [...bob(m), ...blink({ at: 400 })] }),

  // Typing; components/mascot also replays `typing()` each time a test finishes.
  grading: () => ({
    settle: "hold",
    tracks: [
      ...swing("right", [0, -5, 2, -5, 2, 0], { duration: 900 }),
      ...swing("left", [0, -5, 2, -5, 2, 0], { at: 120, duration: 900 }),
      ...nod([0, 1.5, 0, 1.5, 0], { duration: 900 }),
      ...pop("whoosh", { at: 200, duration: 420, stagger: 120 }),
    ],
  }),

  // AC 100/100: the spike's choreography (docs/report/assets/phase-7/animation-spike).
  celebrate: (m) => ({
    settle: "hold",
    tracks: [
      ...hop(m),
      ...wag([0, 6, -5, 3, 0], { at: 150 }),
      ...swing("left", [0, -16, 10, -10, 5, 0], { at: 350, duration: 1500 }),
      ...pop("spark", { at: 250, stagger: 120 }),
    ],
  }),

  // WA: scratches her head while the bug flies off.
  partial: () => ({
    settle: "hold",
    tracks: [
      ...swing("right", [0, -8, 4, -8, 4, 0], { at: 100, duration: 1200 }),
      ...tilt([0, 3, 0], { duration: 1300 }),
      { target: ["bug"], origin: "center", at: 0, duration: 900, ease: "enter", x: [-90, 0], y: [70, 0], opacity: [0, 1] },
      { target: ["trail"], origin: "center", at: 500, duration: 500, opacity: [0, 1] },
      ...pop("drop", { at: 800 }),
    ],
  }),

  // TLE: a long yawn, the Zs float up, the hourglass rocks.
  sleepy: () => ({
    settle: "hold",
    tracks: [
      ...tilt([0, -4, 0], { duration: 1600 }),
      ...drift("zed", { at: 300, duration: 700, stagger: 250 }),
      ...pop("drop", { at: 900 }),
      ...rock("hourglass", [30, 186], [0, -5, 4, 0], { duration: 1000 }),
    ],
  }),

  // MLE: the belly swells twice.
  stuffed: () => ({
    settle: "hold",
    tracks: [
      { target: ["body"], origin: [100, 184], at: 0, duration: 1300, scaleX: [1, 1.07, 0.98, 1.03, 1], scaleY: [1, 1.04, 0.99, 1.02, 1] },
      ...nod([0, -2, 0, -1, 0], { duration: 1300 }),
      ...pop("puff", { at: 300, stagger: 150 }),
    ],
  }),

  // RE: she wobbles, the stars turn over her head.
  dizzy: (m) => ({
    settle: "hold",
    tracks: [
      ...sway(m, [0, -3, 3, -2, 0], { duration: 1800 }),
      ...tilt([0, 5, -5, 4, 0], { duration: 1800 }),
      ...spin("star", { stagger: 100 }),
      ...pop("star", { stagger: 100 }),
    ],
  }),

  // CE: struggles in the cord.
  tangled: (m) => ({
    settle: "hold",
    tracks: [...shake(m, [0, -3, 3, -3, 3, -2, 0], { at: 100 }), ...pop("squiggle", { at: 400 }), ...pop("drop", { at: 700 })],
  }),

  // SE / error page: a small bow.
  sorry: () => ({ settle: "hold", tracks: [...nod([0, 5, 0]), ...pop("drop", { at: 500 })] }),

  // Quiz 100 %.
  party: (m) => ({
    settle: "hold",
    tracks: [
      ...hop(m, { height: 20, duration: 1300 }),
      ...drift("confetti", { at: 100, duration: 700, stagger: 60, from: -26, turn: -40 }),
      ...rock("party-hat", [88, 46], [0, -10, 8, -4, 0], { at: 300, duration: 1000 }),
    ],
  }),

  // Quiz ≥ 80 %: chest out, chin up.
  proud: (m) => ({
    settle: "hold",
    tracks: [
      { target: ["naomi"], origin: m.ground, at: 0, duration: 900, y: [0, -5, 0], scaleY: [1, 1.03, 1] },
      ...tilt([0, -4, 0], { duration: 1100 }),
      ...pop("spark", { at: 500, stagger: 150 }),
    ],
  }),

  // Quiz 50–79 %: fist pump. Outward (clockwise for her left arm): turning
  // the raised fist inward hides it behind the eye bump.
  cheer: (m) => ({
    settle: "hold",
    tracks: [...swing("left", [0, 10, -3, 10, -3, 0]), ...bob(m, { duration: 600, height: 5 }), ...pop("whoosh", { at: 200 })],
  }),

  // Quiz < 50 %: hugs the heart.
  comfort: () => ({
    settle: "hold",
    tracks: [...pulse("heart", [1, 1.12, 1, 1.08, 1], { at: 100 }), ...tilt([0, -3, 0], { duration: 1600 })],
  }),

  // Quiz time ran out: jumps, the clock rings.
  startled: (m) => ({
    settle: "hold",
    tracks: [
      { target: ["naomi"], origin: m.ground, at: 0, duration: 450, ease: ["exit", "overshoot"], y: [0, -12, 0], scaleY: [1, 1.08, 1] },
      ...(m.shadow ? [{ target: ["shadow"], origin: m.shadow, at: 0, duration: 450, scaleX: [1, 0.8, 1] }] : []),
      ...pop("bang", { at: 80, duration: 400 }),
      ...rock("alarm-clock", "center", [0, -9, 9, -9, 9, -5, 0], { duration: 800 }),
    ],
  }),

  // Streak kept: raises the torch, the flame flickers.
  fire: (m) => ({
    settle: "hold",
    tracks: [
      ...swing("left", [0, -8, 4, 0], { duration: 900 }),
      { target: ["flame"], origin: "base", at: 0, duration: 1400, scaleX: [1, 0.92, 1.06, 0.95, 1], scaleY: [1, 1.14, 0.94, 1.08, 1] },
      ...bob(m, { duration: 700, height: 4 }),
    ],
  }),

  // Streak lost: head droops, then lifts again.
  sad: () => ({
    settle: "hold",
    tracks: [
      ...nod([0, 4, 4, 0], { duration: 1800 }).map((t) => ({ ...t, times: [0, 0.3, 0.7, 1] })),
      ...drift("smoke", { at: 200, duration: 1200 }),
      ...pop("drop", { at: 700, duration: 500 }),
    ],
  }),

  // Ranked up: jumps on the podium, which gives a little on landing.
  levelup: (m) => ({
    settle: "hold",
    tracks: [
      ...hop(m, { height: 24 }),
      { target: ["podium"], origin: [100, 194], at: 0, duration: 1400, times: [0, 0.74, 0.82, 1], scaleY: [1, 1, 0.95, 1] },
      ...pop("whoosh", { at: 100 }),
      ...pop("spark", { at: 300, stagger: 120 }),
    ],
  }),

  // Certificate: the cap drops on, the diploma goes up.
  graduate: (m) => ({
    settle: "hold",
    tracks: [
      { target: ["mortarboard"], origin: "center", at: 0, duration: 800, ease: "overshoot", y: [-34, 0], rotate: [-18, 0], opacity: [0, 1] },
      ...swing("right", [0, -10, 0], { at: 700, duration: 900 }),
      ...pop("spark", { at: 900, stagger: 150 }),
      ...bob(m, { at: 700, duration: 900 }),
    ],
  }),

  // 404: looks around, a question mark appears.
  lost: () => ({ settle: "hold", tracks: [...tilt([0, -5, 5, -3, 0], { duration: 1800 }), ...pop("question", { at: 400 })] }),

  // Empty states: the prop appears, she breathes and blinks.
  empty: (m) => ({ settle: "hold", tracks: emptyTracks(m) }),
  "empty-cart": (m) => ({ settle: "hold", tracks: emptyTracks(m) }),
  "empty-courses": (m) => ({ settle: "hold", tracks: emptyTracks(m) }),
  "empty-notifications": (m) => ({ settle: "hold", tracks: [...emptyTracks(m), ...drift("zed", { at: 400, duration: 700, stagger: 200 })] }),
  "empty-notes": (m) => ({ settle: "hold", tracks: emptyTracks(m) }),
  "empty-search": (m) => ({ settle: "hold", tracks: emptyTracks(m) }),

  // AI assistant streaming: the thought bubble fills in.
  thinking: () => ({ settle: "hold", tracks: [...pop("bubble", { duration: 420, stagger: 180 }), ...tilt([0, 3, 0])] }),

  // AI assistant answered with sources: the book opens up.
  answer: (m) => ({
    settle: "hold",
    tracks: [
      { target: ["book"], origin: "base", at: 0, duration: 500, ease: "overshoot", scale: [0.85, 1], opacity: [0, 1] },
      ...pop("spark", { at: 300, stagger: 150 }),
      ...bob(m, { at: 200 }),
    ],
  }),

  // A greeting is a gesture, not a state: she lowers her hand and rests.
  wave: () => ({
    settle: "rest",
    tracks: [
      ...swing("left", [0, -16, 10, -16, 10, -12, 0], { duration: 1600 }),
      ...tilt([0, -3, 0], { duration: 1600 }),
      ...pop("whoosh", { at: 300, stagger: 120 }),
    ],
  }),

  // Payment went through: hops with the bag, the tick appears.
  paid: (m) => ({
    settle: "hold",
    tracks: [
      ...hop(m, { height: 12, duration: 1000 }),
      ...swing("right", [0, -8, 0], { at: 100, duration: 900 }),
      ...pop("tick", { at: 500 }),
      ...pop("spark", { at: 600, stagger: 150 }),
    ],
  }),

  // Payment failed: puzzled look at the card.
  oops: () => ({
    settle: "hold",
    tracks: [
      ...tilt([0, 6, 0], { duration: 1100 }),
      ...pop("cross", { at: 150 }),
      ...pop("drop", { at: 500 }),
      ...swing("left", [0, 4, -4, 2, 0], { at: 200, duration: 800 }),
    ],
  }),
};

function emptyTracks(m: MoodMeta): Track[] {
  return [
    { target: ["scene"], origin: "base", at: 0, duration: 500, ease: "enter", scale: [0.92, 1], opacity: [0, 1] },
    ...bob(m),
    ...blink({ at: 600 }),
  ];
}

export function reactionFor(mood: Mood, meta: MoodMeta): Reaction {
  return REACTIONS[mood](meta);
}

/** The short burst `grading` replays when the test count moves. */
export function typing(): Track[] {
  return [...swing("right", [0, -5, 0], { duration: 420 }), ...swing("left", [0, -5, 0], { at: 60, duration: 420 })];
}
