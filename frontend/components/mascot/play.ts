// Runs a reaction on a drawing with the Web Animations API.
//
// The animation spike (docs/report/assets/phase-7/animation-spike.md) chose
// `motion/react-mini`, a thin layer over this same API. Everything the
// component needs from it is native — per-segment curves, a `finished`
// promise, `cancel()` — so the component calls the API directly: same engine
// the spike measured, without a 5.3 KB dependency (decisions.md).
import type { Ease, Reaction, Track } from "@/lib/mascot/choreography";
import { LINGER_MS, SWAP_MS } from "@/lib/mascot/choreography";
import { originStyle, startsAway, toKeyframes, trackEnd, type Easing } from "@/lib/mascot/keyframes";

const CURVES: Ease[] = ["standard", "enter", "exit", "overshoot"];

/** The design-system curves, read from globals.css (`--ease-*`). */
function easing(): Easing {
  const style = getComputedStyle(document.documentElement);
  return Object.fromEntries(CURVES.map((c) => [c, style.getPropertyValue(`--ease-${c}`).trim() || "linear"])) as Easing;
}

/** `endsAt`: when the last animation should be over, in ms from the start. */
export type Run = { finished: Promise<void>; cancel: () => void; endsAt: number };

function pieces(drawing: Element, t: Track): Element[] {
  const selector = t.target.map((n) => `[data-layer="${n}"],[data-part="${n}"]`).join(",");
  return Array.from(drawing.querySelectorAll(selector));
}

/** Start `tracks` on the pieces of `drawing`. Returns the animations. */
export function animateTracks(drawing: Element, tracks: readonly Track[], curves = easing()): Animation[] {
  const out: Animation[] = [];
  for (const t of tracks) {
    const frames = toKeyframes(t, curves);
    const { transformBox, transformOrigin } = originStyle(t.origin);
    // Before its delay, a piece that starts away from the drawing (a sparkle
    // at scale 0) must already be there; one that starts at rest must not, or
    // it would hide an earlier track on the same property.
    const fill: FillMode = startsAway(t) ? "backwards" : "none";
    pieces(drawing, t).forEach((el, i) => {
      const style = (el as SVGElement).style;
      style.transformBox = transformBox;
      style.transformOrigin = transformOrigin;
      out.push(el.animate(frames, { duration: t.duration, delay: t.at + i * (t.stagger ?? 0), fill }));
    });
  }
  return out;
}

/**
 * Play a reaction on `drawing`. With `rest`, cross-fade from the mood's
 * drawing to the resting one once the reaction is over; both stay faded
 * (`forwards`) until React swaps the markup, so nothing flashes in between.
 */
export function play(drawing: HTMLElement, reaction: Reaction, rest?: HTMLElement): Run {
  const curves = easing();
  const animations = animateTracks(drawing, reaction.tracks, curves);
  if (rest) {
    const end = Math.max(0, ...reaction.tracks.map((t) => trackEnd(t, pieces(drawing, t).length)));
    const swap: KeyframeAnimationOptions = { delay: end + LINGER_MS, duration: SWAP_MS, easing: curves.standard, fill: "both" };
    animations.push(drawing.animate([{ opacity: 1 }, { opacity: 0 }], swap));
    animations.push(rest.animate([{ opacity: 0 }, { opacity: 1 }], swap));
  }
  const timing = (a: Animation) => a.effect?.getComputedTiming().endTime;
  return {
    finished: Promise.all(animations.map((a) => a.finished)).then(() => undefined),
    cancel: () => animations.forEach((a) => a.cancel()),
    endsAt: Math.max(0, ...animations.map((a) => Number(timing(a) ?? 0))),
  };
}
