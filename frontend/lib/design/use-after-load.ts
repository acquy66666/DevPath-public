"use client";

import { useEffect, useState } from "react";

/**
 * True once the page has finished loading and the browser has a quiet moment.
 *
 * For code that is not in the first screen but should be ready soon after --
 * the header's phone menu, the toast stack. Loading it straight after
 * hydration put its requests in the same moment as the first paint, and a
 * phone on a slow network then shared its bandwidth between them and the
 * page (Phase 7 performance, docs/report/assets/phase-7/performance.md).
 *
 * `now()` lets an early interaction skip the wait.
 */
export function useAfterLoad(): { ready: boolean; now: () => void } {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (ready) return;
    let idle = 0;
    let timer = 0;
    const settle = () => {
      // Safari has no requestIdleCallback.
      if (typeof window.requestIdleCallback === "function") {
        idle = window.requestIdleCallback(() => setReady(true), { timeout: 2000 });
      } else {
        timer = setTimeout(() => setReady(true), 200) as unknown as number;
      }
    };
    if (document.readyState === "complete") settle();
    else window.addEventListener("load", settle, { once: true });
    return () => {
      window.removeEventListener("load", settle);
      if (idle) window.cancelIdleCallback(idle);
      if (timer) clearTimeout(timer);
    };
  }, [ready]);

  return { ready, now: () => setReady(true) };
}
