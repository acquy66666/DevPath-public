"use client";

import { useEffect } from "react";
import { useAnimate } from "motion/react";
import { NaomiFrame } from "./naomi-frame";
import { SWAP, TRACKS, delay, ease, reduced, selector, type Track } from "./tracks";

// Full Motion: the hybrid animate() with independent transform values (y,
// scaleX, rotate...), which is how Motion code is normally written.
function keyframes(t: Track) {
  const frames: Record<string, number[] | string> = {};
  for (const key of ["y", "scaleX", "scaleY", "scale", "rotate", "opacity"] as const) {
    const list = t[key];
    if (list) frames[key] = list;
  }
  // Motion writes `transform-box: fill-box` inline on any SVG element it
  // transforms unless told otherwise, which turns the stylesheet's pivot
  // (drawing coordinates, view-box) into an offset from the layer's own box:
  // the arm swings from the wrong point and the shadow slides sideways.
  if (t.origin !== "center") frames.transformBox = "view-box";
  return frames;
}

export function NaomiMotion({ celebrate, rest }: { celebrate: string; rest: string }) {
  const [scope, animate] = useAnimate<HTMLDivElement>();

  useEffect(() => {
    if (reduced()) return;
    for (const t of TRACKS) {
      animate(selector(t), keyframes(t), {
        duration: t.duration / 1000,
        delay: delay(t),
        times: t.times,
        ease: ease(t),
      });
    }
    const swap = { delay: SWAP.at, duration: SWAP.duration, ease: SWAP.ease };
    animate('[data-part="celebrate"]', { opacity: [1, 0] }, swap);
    animate('[data-part="rest"]', { opacity: [0, 1] }, swap);
  }, [animate]);

  return <NaomiFrame scope={scope} celebrate={celebrate} rest={rest} playing />;
}
