/**
 * The stand-in picture of a course without a thumbnail: a few lines of
 * "code" and a pair of brackets, tinted with one of the design system's
 * illustration families.
 *
 * Every class is written out in full: Tailwind only ships the classes it can
 * find spelled out in the source. Only steps the design system defines (100,
 * 200, 500, 700) are used, and never turmeric -- that one is for rewards.
 */
export interface CoverTint {
  /** The family's name, for tests and for reading the markup. */
  family: "jade" | "blue" | "violet" | "rose" | "amber" | "green";
  /** The tile itself. */
  background: string;
  /** The first and the short trailing bar. */
  strong: string;
  /** The indented bars. */
  soft: string;
  /** The last bar. */
  ink: string;
  /** The brackets in the corner, as pale as the indented bars. */
  glyph: string;
}

export const COVER_TINTS: readonly CoverTint[] = [
  { family: "jade", background: "bg-jade-100", strong: "bg-jade-500", soft: "bg-jade-200", ink: "bg-jade-700", glyph: "text-jade-200" },
  { family: "blue", background: "bg-blue-100", strong: "bg-blue-500", soft: "bg-blue-200", ink: "bg-blue-700", glyph: "text-blue-200" },
  { family: "violet", background: "bg-violet-100", strong: "bg-violet-500", soft: "bg-violet-200", ink: "bg-violet-700", glyph: "text-violet-200" },
  { family: "rose", background: "bg-rose-100", strong: "bg-rose-500", soft: "bg-rose-200", ink: "bg-rose-700", glyph: "text-rose-200" },
  { family: "amber", background: "bg-amber-100", strong: "bg-amber-500", soft: "bg-amber-200", ink: "bg-amber-700", glyph: "text-amber-200" },
  { family: "green", background: "bg-green-100", strong: "bg-green-500", soft: "bg-green-200", ink: "bg-green-700", glyph: "text-green-200" },
];

/** Brackets of the languages DevPath teaches, none tied to one of them. */
export const COVER_GLYPHS: readonly string[] = ["{}", "()", "[]", "</>", "=>", "#!"];

function hash(key: string): number {
  let value = 0;
  for (const char of key) value = (value * 31 + (char.codePointAt(0) ?? 0)) >>> 0;
  return value;
}

/**
 * Same key, same cover, on every page and every render: the course keeps its
 * colour on the card, its own page and the cart. The glyph is drawn from a
 * second, independent split of the hash, so two courses of one colour still
 * tend to differ.
 */
export function coverFor(key: string): { tint: CoverTint; glyph: string } {
  const value = hash(key);
  return {
    tint: COVER_TINTS[value % COVER_TINTS.length],
    glyph: COVER_GLYPHS[Math.floor(value / COVER_TINTS.length) % COVER_GLYPHS.length],
  };
}
