import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { Slot } from "radix-ui"

import { cn } from "@/lib/utils"

// Design system, component Badge: a word or two of status beside the name of
// a thing. 22px, fully round, 12px semibold, never wraps. Not a button -- it
// only reacts to the pointer when it is a link (`asChild` around a Link).
// Verdicts of graded code are not badges: they carry a code and an icon.
const badgeVariants = cva(
  "group/badge inline-flex h-5.5 w-fit shrink-0 items-center justify-center gap-1 overflow-hidden rounded-full border border-transparent px-2.5 text-xs leading-4 font-semibold whitespace-nowrap tabular-nums transition-colors has-data-[icon=inline-end]:pr-2 has-data-[icon=inline-start]:pl-2 [&>svg]:pointer-events-none [&>svg]:size-3!",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground [a]:hover:bg-primary-hover",
        secondary:
          "bg-secondary text-secondary-foreground [a]:hover:bg-secondary-hover",
        outline: "border-border-strong text-foreground [a]:hover:bg-accent",
        muted: "bg-muted text-muted-foreground [a]:hover:bg-accent",
        success: "bg-success-soft text-success-text",
        warning: "bg-warning-soft text-warning-text",
        info: "bg-info-soft text-info-text",
        destructive: "bg-destructive-soft text-destructive-text",
        reward: "bg-reward text-reward-foreground",
        streak: "bg-reward-soft text-streak-text [&>svg]:text-streak",
        ghost: "[a]:hover:bg-accent",
        link: "text-link underline-offset-4 [a]:hover:underline",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

function Badge({
  className,
  variant = "default",
  asChild = false,
  ...props
}: React.ComponentProps<"span"> &
  VariantProps<typeof badgeVariants> & { asChild?: boolean }) {
  const Comp = asChild ? Slot.Root : "span"

  return (
    <Comp
      data-slot="badge"
      data-variant={variant}
      className={cn(badgeVariants({ variant }), className)}
      {...props}
    />
  )
}

export { Badge, badgeVariants }
