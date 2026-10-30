"use client";

import { lazy, Suspense } from "react";

import type { Mood } from "@/lib/mascot/moods";
import { cn } from "@/lib/utils";

import type { MascotSize } from "./mascot";

const Still = lazy(() => import("./still").then((m) => ({ default: m.NaomiStill })));

const SIZE: Record<MascotSize, string> = { sm: "size-12", md: "size-32", lg: "size-50" };

/**
 * <NaomiStill> with its code out of the first load: the server still draws
 * her into the HTML, and the browser fetches her component (and her mood's
 * drawing) to hydrate that spot only once it is reached. Every page's error
 * boundary and the home page's example carry her, and those few kilobytes,
 * on every first load, were enough to cost the home page a round trip on a
 * slow phone (Phase 7 performance, docs/report/assets/phase-7/performance.md).
 *
 * Until then -- a client-rendered empty state, say -- an empty box of her
 * size holds her place, so nothing moves when she arrives.
 */
export function LazyNaomiStill(props: { mood: Mood; size?: MascotSize; label?: string | boolean; className?: string }) {
  return (
    <Suspense
      fallback={
        <span
          aria-hidden
          className={cn("pointer-events-none relative inline-block shrink-0", SIZE[props.size ?? "md"], props.className)}
        />
      }
    >
      <Still {...props} />
    </Suspense>
  );
}
