import { coverFor } from "@/lib/courses/cover";
import { cn } from "@/lib/utils";

/** Bar thickness, gaps and glyph size per place the cover is drawn. */
const SCALE = {
  /** A 64px tag beside the course title: the learning page's top bar. */
  xs: { box: "gap-[3px] px-2 py-[7px]", bar: "h-[3px]", glyph: "right-1.5 bottom-0 text-sm leading-[1.125rem]" },
  /** A thumbnail beside a row: the cart, a wide recommendation card. */
  sm: { box: "gap-1 p-2.5", bar: "h-1", glyph: "right-2 bottom-0 text-2xl" },
  /** A course card. */
  md: { box: "gap-2 px-5.5 py-5", bar: "h-2", glyph: "right-4.5 bottom-1.5 text-[3.5rem] leading-[4rem]" },
  /** The price card of the course page. */
  lg: { box: "gap-2.5 px-6 py-5.5", bar: "h-2.5", glyph: "right-5 bottom-1.5 text-[4rem] leading-[4.5rem]" },
} as const;

/**
 * The picture at the top of a course: its thumbnail when it has one, or else
 * a tile of its own -- a few lines of "code" and a pair of brackets, in one of
 * the design system's illustration tints (`lib/courses/cover.ts`).
 *
 * The course builder has no thumbnail upload, so in practice every course is
 * the "else", and a catalogue of identical boxes reads as a page that failed
 * to load. Keyed by course, not category: the category is already written
 * under the picture, and nine courses on one subject made a whole row of the
 * same tile. One course keeps its cover on the card, its page and the cart.
 */
export function CourseCover({
  thumbnailUrl,
  colorKey,
  size = "md",
  className,
}: {
  thumbnailUrl: string | null;
  /** What picks the tint and the glyph -- the course id. */
  colorKey: string;
  size?: keyof typeof SCALE;
  className?: string;
}) {
  if (thumbnailUrl) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={thumbnailUrl}
        alt=""
        className={cn("aspect-video w-full bg-muted object-cover", className)}
      />
    );
  }

  const { tint, glyph } = coverFor(colorKey);
  const scale = SCALE[size];
  const bar = cn("block rounded-full", scale.bar);

  return (
    <div
      aria-hidden
      className={cn(
        "relative flex aspect-video w-full flex-col overflow-hidden",
        tint.background,
        scale.box,
        className,
      )}
    >
      <span className={cn(bar, tint.strong, "w-[38%]")} />
      <span className={cn(bar, tint.soft, "ml-[10%] w-[52%]")} />
      <span className="ml-[10%] flex gap-1.5">
        <span className={cn(bar, tint.soft, "w-[30%]")} />
        <span className={cn(bar, tint.strong, "w-[14%]")} />
      </span>
      <span className={cn(bar, tint.ink, "w-[24%]")} />
      <span
        className={cn(
          "absolute font-mono font-semibold tracking-tighter select-none",
          tint.glyph,
          scale.glyph,
        )}
      >
        {glyph}
      </span>
    </div>
  );
}
