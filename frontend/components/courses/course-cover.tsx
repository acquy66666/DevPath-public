import { GraduationCap } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * Spelled out rather than built from a colour name: Tailwind only ships the
 * classes it can find written down in the source.
 */
const PALETTE = [
  { background: "from-indigo-50 to-indigo-200", icon: "text-indigo-500" },
  { background: "from-sky-50 to-sky-200", icon: "text-sky-600" },
  { background: "from-emerald-50 to-emerald-200", icon: "text-emerald-600" },
  { background: "from-amber-50 to-amber-200", icon: "text-amber-600" },
  { background: "from-rose-50 to-rose-200", icon: "text-rose-500" },
  { background: "from-teal-50 to-teal-200", icon: "text-teal-600" },
  { background: "from-violet-50 to-violet-200", icon: "text-violet-500" },
  { background: "from-lime-50 to-lime-200", icon: "text-lime-700" },
];

/**
 * Same key, same colour, on every page and every render. Pale on purpose: the
 * rest of the site is black on white, and a row of saturated tiles shouted
 * over the course titles under them.
 */
function paletteFor(key: string) {
  let hash = 0;
  for (const char of key) hash = (hash * 31 + (char.codePointAt(0) ?? 0)) >>> 0;
  return PALETTE[hash % PALETTE.length];
}

/**
 * The picture at the top of a course: its thumbnail when it has one, or else
 * a pale gradient of its own.
 *
 * The course builder has no thumbnail upload, so in practice every course is
 * the "else" -- and a catalogue of identical grey boxes reads as a page that
 * failed to load. Keyed by course, not category: the category is already the
 * badge under the picture, and nine courses on one subject made a whole row
 * of the same tile. One course keeps its colour on the card, its page and the
 * cart.
 */
export function CourseCover({
  thumbnailUrl,
  colorKey,
  className,
  iconClassName,
}: {
  thumbnailUrl: string | null;
  /** What picks the colour -- the course id. */
  colorKey: string;
  className?: string;
  iconClassName?: string;
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

  const palette = paletteFor(colorKey);

  return (
    <div
      className={cn(
        "flex aspect-video w-full items-center justify-center bg-gradient-to-br",
        palette.background,
        className,
      )}
      aria-hidden
    >
      <GraduationCap className={cn("size-10", palette.icon, iconClassName)} />
    </div>
  );
}
