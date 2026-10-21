"use client";

import { useEffect } from "react";
import { useAnimate } from "motion/react-mini";
import { NaomiFrame } from "./naomi-frame";
import { SWAP, TRACKS, delay, ease, reduced, selector, type Track } from "./tracks";

// motion/react-mini: a thin layer over the Web Animations API. It animates real
// CSS properties only, so the transform goes through the individual transform
// properties (translate / scale / rotate), which Chrome applies to SVG too.
function keyframes(t: Track) {
  const n = t.times.length;
  const at = (list: number[] | undefined, i: number, fallback: number) => (list ? list[i] : fallback);
  const frames: Record<string, string[] | number[]> = {};
  if (t.y) frames.translate = t.y.map((y) => `0px ${y}px`);
  if (t.scale || t.scaleX || t.scaleY) {
    frames.scale = Array.from({ length: n }, (_, i) =>
      t.scale ? `${t.scale[i]}` : `${at(t.scaleX, i, 1)} ${at(t.scaleY, i, 1)}`,
    );
  }
  if (t.rotate) frames.rotate = t.rotate.map((r) => `${r}deg`);
  if (t.opacity) frames.opacity = t.opacity;
  return frames;
}

export function NaomiMini({ celebrate, rest }: { celebrate: string; rest: string }) {
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
