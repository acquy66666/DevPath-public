import type { ComponentProps, ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * A block standing in for content that is on its way: `muted`, with the size
 * and the radius of the thing it replaces, so nothing moves when the data
 * lands (design system, "Trạng thái và tương tác"). Size it in `className`
 * from the real component -- a line of `text-body` is 24px tall, a button
 * 36px, a card `rounded-lg`. Pulses only for people who have not asked for
 * less motion. Hidden from assistive tech: say "loading" once per region with
 * `SkeletonRegion`, not once per block.
 */
function Skeleton({ className, ...props }: ComponentProps<"div">) {
  return (
    <div
      data-slot="skeleton"
      aria-hidden
      className={cn("rounded-md bg-muted motion-safe:animate-pulse", className)}
      {...props}
    />
  );
}

/**
 * A line of text in skeleton form: the line box of the type style, with the
 * grey bar at the height of the letters, so a column of these stacks exactly
 * like the paragraph it replaces. `size` is the type style's line height.
 */
function SkeletonText({
  size = "body",
  className,
}: {
  size?: "h1" | "h2" | "h3" | "title" | "body" | "body-sm" | "caption";
  className?: string;
}) {
  return (
    <div aria-hidden className={cn("flex items-center", LINE[size], className)}>
      <div data-slot="skeleton" className={cn("h-[0.75em] w-full rounded-xs bg-muted motion-safe:animate-pulse", FONT[size])} />
    </div>
  );
}

// Line box per type style (globals.css). The bar inside takes 0.75em of the
// style's font size: about the height of a lowercase letter with its marks.
const LINE = {
  h1: "h-10",
  h2: "h-8",
  h3: "h-7",
  title: "h-6",
  body: "h-6",
  "body-sm": "h-5",
  caption: "h-[1.125rem]",
} as const;
const FONT = {
  h1: "text-h1",
  h2: "text-h2",
  h3: "text-h3",
  title: "text-title",
  body: "text-body",
  "body-sm": "text-body-sm",
  caption: "text-caption",
} as const;

/**
 * A word-sized bar inside a real line of text -- a number not yet known in a
 * tile, a date in a row. Inline, so the line keeps exactly the height its type
 * style gives it.
 */
function SkeletonInline({ className }: { className?: string }) {
  return (
    <span
      data-slot="skeleton"
      aria-hidden
      className={cn("inline-block h-[0.75em] w-[5ch] rounded-xs bg-muted align-[-0.05em] motion-safe:animate-pulse", className)}
    />
  );
}

/** One "loading" announcement for a whole region of skeletons. */
function SkeletonRegion({
  label,
  className,
  children,
}: {
  label: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div role="status" aria-live="polite" className={className}>
      <span className="sr-only">{label}</span>
      {children}
    </div>
  );
}

export { Skeleton, SkeletonInline, SkeletonRegion, SkeletonText };
