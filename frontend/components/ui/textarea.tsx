import * as React from "react"

import { fieldClass } from "@/components/ui/input"
import { cn } from "@/lib/utils"

/** An `Input` that grows with its text, from 96px. */
function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(fieldClass, "field-sizing-content min-h-24 px-3 py-2", className)}
      {...props}
    />
  )
}

export { Textarea }
