import * as React from "react"

import { cn } from "@/lib/utils"

// Design system, progress bar. The fill is a full-width bar pushed left by
// `translateX`, not a `width` that changes: only transform and opacity move
// (components/Motion). A change glides over duration-progress on
// ease-standard; with reduced motion it jumps straight to the value.

function Progress({
  value,
  max = 100,
  className,
  indicatorClassName,
  ...props
}: Omit<React.ComponentProps<"div">, "role" | "children"> & {
  value: number
  max?: number
  /** Colour of the fill; `bg-primary` unless told otherwise. */
  indicatorClassName?: string
}) {
  const ratio = max > 0 ? Math.min(Math.max(value / max, 0), 1) : 0

  return (
    <div
      data-slot="progress"
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={max}
      aria-valuenow={value}
      className={cn("relative h-2 overflow-hidden rounded-full bg-accent", className)}
      {...props}
    >
      <div
        data-slot="progress-indicator"
        className={cn(
          "h-full w-full rounded-full bg-primary transition-transform duration-progress ease-standard motion-reduce:transition-none",
          indicatorClassName
        )}
        style={{ transform: `translateX(-${(1 - ratio) * 100}%)` }}
      />
    </div>
  )
}

export { Progress }
