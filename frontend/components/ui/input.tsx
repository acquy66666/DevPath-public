import * as React from "react"

import { cn } from "@/lib/utils"

// Design system, component FormField: 40px tall, 16px text (smaller makes iOS
// zoom in on focus), `card` inside an `input` border that reaches 3:1, a
// hairline shadow. Focus is the site-wide ring; an invalid field says so with
// `aria-invalid`, which also turns the border `destructive`.
const fieldClass =
  "w-full min-w-0 rounded-md border border-input bg-card text-base text-foreground shadow-xs transition-[border-color,box-shadow] placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:border-border-strong disabled:bg-muted disabled:text-muted-foreground disabled:shadow-none aria-invalid:border-destructive"

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        fieldClass,
        "h-10 px-3 py-2 file:mr-3 file:inline-flex file:h-7 file:border-0 file:bg-transparent file:text-sm file:font-semibold file:text-foreground",
        className
      )}
      {...props}
    />
  )
}

export { Input, fieldClass }
