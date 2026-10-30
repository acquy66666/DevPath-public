"use client";

import { Suspense, use } from "react";

import { MOOD_META, type Mood } from "@/lib/mascot/moods";
import { cn } from "@/lib/utils";

import { loadArt, SERVER_ART } from "./load-art";
import type { MascotSize } from "./mascot";

const SIZE: Record<MascotSize, string> = { sm: "size-12", md: "size-32", lg: "size-50" };

/**
 * Naomi standing still, and nothing else: the same markup as a <Mascot>
 * without an event, but none of its reaction code (choreography, Web
 * Animations, the on-screen watch). For the places where she never reacts --
 * empty states, 404 and error pages, the home page's example -- so that a
 * first load does not carry the animated component. Turbopack had put three
 * copies of it on the home page alone, one per boundary (~6 KB gzip each;
 * Phase 7 performance, docs/report/assets/phase-7/performance.md). Use it
 * through <LazyNaomiStill>, which keeps even this out of the first load.
 *
 * A Client Component on purpose, like <Mascot>: the server still draws her
 * into the HTML, but the RSC payload carries only the mood. As a Server
 * Component her ~8 KB of SVG went down twice, in the HTML and in the payload,
 * and the course page's document grew past a round trip (measured: first
 * paint 150 ms later). The browser fetches only her mood's drawing.
 */
export function NaomiStill({
  mood,
  size = "md",
  label,
  className,
}: {
  mood: Mood;
  size?: MascotSize;
  /** As on <Mascot>: decorative unless given; `true` uses the mood's description. */
  label?: string | boolean;
  className?: string;
}) {
  const name = label === true ? MOOD_META[mood].label : label || undefined;
  return (
    <span
      data-mascot=""
      data-size={size}
      role={name ? "img" : undefined}
      aria-label={name}
      aria-hidden={name ? undefined : true}
      className={cn("pointer-events-none relative inline-block shrink-0 select-none", SIZE[size], className)}
    >
      <Suspense fallback={null}>
        <Drawing mood={mood} />
      </Suspense>
    </span>
  );
}

function Drawing({ mood }: { mood: Mood }) {
  const art = SERVER_ART ? SERVER_ART[mood] : use(loadArt(mood));
  return (
    <span data-phase="still" data-mood={mood} className="absolute inset-0">
      <span className="absolute inset-0" dangerouslySetInnerHTML={{ __html: art }} />
    </span>
  );
}
