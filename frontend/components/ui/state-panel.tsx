import type { ReactNode } from "react";

import { Mascot } from "@/components/mascot/mascot";
import { cn } from "@/lib/utils";

/**
 * The body of a 404 or an error page: what happened, what to do next, and
 * Naomi -- `lost` holding her map upside down for a page that is not there,
 * `sorry` with her "đang sửa" sign for a failure on our side (reaction map,
 * design doc §5). Still pose: the page did not just do something, it simply
 * is not there.
 *
 * `mood={null}` in the instructor and admin areas, where Naomi only shows up
 * in empty states. `code` is the short label above the title ("404"), set in
 * mono like every other code. `detail` is a line for support, e.g. the error
 * digest. `compact` drops the page-sized padding, for a boundary that renders
 * inside a layout that already has it.
 *
 * Naomi stands beside the text once the panel itself is 576px wide (a
 * container query, not the viewport: the sign-in card is narrow on any
 * screen), above it below that.
 */
export function StatePanel({
  mood,
  code,
  title,
  titleAs: Title = "h1",
  children,
  actions,
  detail,
  compact = false,
  className,
}: {
  mood: "lost" | "sorry" | null;
  code?: string;
  title: ReactNode;
  titleAs?: "h1" | "h2";
  children?: ReactNode;
  actions?: ReactNode;
  detail?: ReactNode;
  compact?: boolean;
  className?: string;
}) {
  return (
    <div
      data-slot="state-panel"
      className={cn("@container mx-auto w-full", mood ? "max-w-3xl" : "max-w-xl", compact ? "py-2" : "px-4 py-12 md:py-20", className)}
    >
      <div className={cn("grid items-center gap-6", mood && "@xl:grid-cols-[auto_minmax(0,1fr)] @xl:gap-10")}>
        {mood ? <Mascot mood={mood} size="lg" className="size-32 @xl:size-50" /> : null}
        <div className="flex min-w-0 flex-col gap-2">
          {code ? <p className="font-mono text-eyebrow text-muted-foreground uppercase">{code}</p> : null}
          <Title className={cn("text-balance text-foreground", Title === "h1" ? "text-h1" : "text-h2")}>{title}</Title>
          {children ? <div className="max-w-prose text-body text-muted-foreground">{children}</div> : null}
          {actions ? <div className="mt-4 flex flex-wrap gap-3">{actions}</div> : null}
          {detail ? <p className="mt-2 font-mono text-caption text-muted-foreground">{detail}</p> : null}
        </div>
      </div>
    </div>
  );
}
