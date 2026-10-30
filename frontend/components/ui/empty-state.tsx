import type { ReactNode } from "react";

import { LazyNaomiStill } from "@/components/mascot/lazy-still";
import type { Mood } from "@/lib/mascot/moods";
import { cn } from "@/lib/utils";

/** Naomi waiting, alone or beside the prop of the place she is in. */
export type EmptyMood = Extract<Mood, "empty" | `empty-${string}`>;

const NAOMI = { lg: undefined, md: "size-20", sm: "size-16" } as const;

/**
 * A list, a page or a panel with nothing in it yet (design system, "Giọng
 * văn": "Chưa có … nào" plus the way to make the first one). Naomi sits beside
 * the words in her still pose, with the prop of the place: a cart, a closed
 * book, a sleeping bell, a notebook, a magnifying glass. She never reacts
 * here -- an empty list is not something that just happened -- and she is
 * decorative: the title says it all.
 *
 * - `lg`: the main content of a learner's page. Naomi 128px.
 * - `md`: a tab, a card, a work screen of the instructor or admin areas
 *   (where Naomi appears only in empty states, and stays small). 80px.
 * - `sm`: a dropdown. 64px, always above the text.
 *
 * `lg` and `md` put Naomi beside the text once the box is 448px wide -- a
 * container query, so the same list can be a page on a laptop and a column
 * on a phone. `framed={false}` when the empty state already sits inside a
 * card or a bordered panel.
 */
export function EmptyState({
  mood = "empty",
  title,
  description,
  action,
  size = "lg",
  framed = true,
  titleAs: Title = "p",
  className,
}: {
  mood?: EmptyMood;
  title: ReactNode;
  description?: ReactNode;
  /** Buttons or links: the way to make the first one. */
  action?: ReactNode;
  size?: "lg" | "md" | "sm";
  framed?: boolean;
  titleAs?: "p" | "h2" | "h3";
  className?: string;
}) {
  const row = size !== "sm";
  return (
    <div
      data-slot="empty-state"
      className={cn("@container", framed && "rounded-lg border border-dashed border-border-strong", className)}
    >
      <div
        className={cn(
          "flex flex-col items-center text-center",
          size === "lg" && "gap-4 px-6 py-10 @md:gap-8 @md:px-10",
          size === "md" && "gap-3 px-5 py-8 @md:gap-6 @md:px-8",
          size === "sm" && "gap-2 px-4 py-6",
          row && "@md:flex-row @md:justify-center @md:text-left",
        )}
      >
        <LazyNaomiStill mood={mood} size="md" className={NAOMI[size]} />
        <div className={cn("flex min-w-0 flex-col items-center gap-1", row && "@md:items-start")}>
          <Title className={cn("text-balance text-foreground", size === "sm" ? "text-body-sm font-semibold" : "text-title")}>
            {title}
          </Title>
          {description ? <div className="max-w-md text-body-sm text-muted-foreground">{description}</div> : null}
          {action ? (
            <div className={cn("mt-3 flex flex-wrap justify-center gap-3", row && "@md:justify-start")}>{action}</div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
