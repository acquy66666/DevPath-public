import type { Mood } from "@/lib/mascot/moods";

import { ART } from "./art";

// Naomi's drawings, shared by the animated <Mascot> and the still
// <NaomiStill>: one chunk per mood in the browser, every drawing at once on
// the server.

const loaded = new Map<Mood, Promise<string>>();

/**
 * One chunk per mood, cached. The promise records its own result the way
 * React's `use()` reads it (`status`, `value`), so a drawing that has loaded
 * renders synchronously instead of suspending again.
 */
export function loadArt(mood: Mood): Promise<string> {
  let art = loaded.get(mood);
  if (!art) {
    const next: Promise<string> = ART[mood]().then(
      (m) => {
        Object.assign(next, { status: "fulfilled", value: m.default });
        return m.default;
      },
      (error: unknown) => {
        loaded.delete(mood); // let a later mount try again
        throw error;
      },
    );
    loaded.set(mood, next);
    art = next;
  }
  return art;
}

/**
 * The server reads every drawing synchronously, so server rendering never
 * waits on a chunk: the still pose is in the HTML from the first request after
 * a start. (React may still move a finished boundary to the end of the HTML
 * when the page before it is over 12,800 bytes; an inline script shows it
 * before hydration.) Next replaces `typeof window` at build time, so the
 * browser bundle drops this branch and never contains the module — capture.cjs
 * fails if a chunk holds more than one drawing.
 */
export const SERVER_ART: Record<Mood, string> | null =
  typeof window === "undefined"
    ? // eslint-disable-next-line @typescript-eslint/no-require-imports
      (require("./art/server") as typeof import("./art/server")).ART_SYNC
    : null;
