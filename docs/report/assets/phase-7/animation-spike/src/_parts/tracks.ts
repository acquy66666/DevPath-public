import choreography from "../choreography.json";
import { EASE } from "../_gen/easing";

// Shared by the two Motion variants: read the choreography, hand back what
// each animate() call needs. The CSS variant gets the same data as keyframes,
// written by run.cjs.

export type Track = (typeof choreography.tracks)[number] & {
  y?: number[];
  scaleX?: number[];
  scaleY?: number[];
  scale?: number[];
  rotate?: number[];
  opacity?: number[];
  stagger?: number;
};

export const TRACKS = choreography.tracks as Track[];
export const SWAP = {
  at: choreography.swapAtMs / 1000,
  duration: choreography.swapMs / 1000,
  ease: EASE[choreography.swapEase],
};

// The spark layer is three <g class="spark"> wrappers; every other layer is
// one element with that id.
export const selector = (t: Track) => (t.layer === "spark" ? ".spark" : `#${t.layer}`);

export const ease = (t: Track) => t.ease.map((name) => EASE[name]);

/** Delay in seconds, staggered per element when the track has a stagger. */
export const delay = (t: Track) =>
  t.stagger ? (i: number) => (t.delay + i * t.stagger!) / 1000 : t.delay / 1000;

export const reduced = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
