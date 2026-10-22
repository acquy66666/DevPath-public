/**
 * The design-system names that are not Tailwind's own, for code that has to
 * know them: `cn()` merges classes by name, and a name it has never heard of
 * is guessed at -- `text-body-sm` reads to it as a text colour, so
 * `cn("text-body-sm", "text-muted-foreground")` would drop the size.
 *
 * The values live in app/globals.css; tokens.test.ts keeps these lists equal
 * to the design system's tokens.json.
 */

/** Type scale: `text-display` … `text-eyebrow`, `text-code`, `text-numeral`. */
export const TEXT_STYLES = [
  "display",
  "h1",
  "h2",
  "h3",
  "title",
  "body-lg",
  "body",
  "body-sm",
  "caption",
  "eyebrow",
  "code",
  "code-sm",
  "numeral",
  "cert-title",
] as const;

/** `duration-instant` … `duration-mascot`. */
export const DURATIONS = ["instant", "fast", "base", "slow", "progress", "mascot"] as const;

/** `ease-standard` … `ease-overshoot`. */
export const EASINGS = ["standard", "enter", "exit", "overshoot"] as const;

/** What `cn()` adds to tailwind-merge's idea of Tailwind (lib/utils.ts). */
export const MERGE_CONFIG = {
  extend: {
    theme: {
      text: [...TEXT_STYLES],
      ease: [...EASINGS],
    },
    classGroups: {
      duration: [{ duration: [...DURATIONS] }],
    },
  },
}
