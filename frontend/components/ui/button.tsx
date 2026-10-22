import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { Slot } from "radix-ui"

import { cn } from "@/lib/utils"

// Design system, component Button (docs/ui-ux/design-system/project/
// components/Button). One `default` (primary) per screen, for that screen's
// main job; `secondary` for the next action in the same group; `outline` for
// neutral ones; `destructive` only behind a confirmation.
//
// Focus is the site-wide ring from globals.css. Hover is `not-disabled:` so a
// disabled button keeps its colour and still shows the not-allowed cursor; the
// 1px press only moves when motion is welcome.
const buttonVariants = cva(
  "group/button inline-flex shrink-0 items-center justify-center rounded-md border border-transparent bg-clip-padding font-semibold whitespace-nowrap transition-[color,background-color,border-color,box-shadow,transform] duration-fast ease-standard select-none motion-safe:active:not-aria-[haspopup]:not-disabled:translate-y-px motion-safe:active:duration-instant disabled:cursor-not-allowed disabled:opacity-50 aria-invalid:border-destructive [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:not-disabled:bg-primary-hover",
        secondary:
          "bg-secondary text-secondary-foreground hover:not-disabled:bg-secondary-hover aria-expanded:bg-secondary-hover",
        outline:
          "border-input bg-card text-foreground shadow-xs hover:not-disabled:bg-accent hover:not-disabled:text-accent-foreground aria-expanded:bg-accent",
        ghost:
          "hover:not-disabled:bg-accent hover:not-disabled:text-accent-foreground aria-expanded:bg-accent aria-expanded:text-accent-foreground",
        destructive:
          "bg-destructive text-destructive-foreground hover:not-disabled:bg-destructive/90",
        link: "text-link underline underline-offset-4 hover:not-disabled:decoration-2",
      },
      // sm 32 · default 36 · lg 44 (the main action on a phone) · icon 36.
      size: {
        default:
          "h-9 gap-2 px-4 text-sm has-data-[icon=inline-end]:pr-3 has-data-[icon=inline-start]:pl-3",
        xs: "h-7 gap-1 px-2 text-xs has-data-[icon=inline-end]:pr-1.5 has-data-[icon=inline-start]:pl-1.5 [&_svg:not([class*='size-'])]:size-3.5",
        sm: "h-8 gap-1.5 px-3 text-[0.8125rem] has-data-[icon=inline-end]:pr-2.5 has-data-[icon=inline-start]:pl-2.5 [&_svg:not([class*='size-'])]:size-4",
        lg: "h-11 gap-2 px-5 text-base has-data-[icon=inline-end]:pr-4 has-data-[icon=inline-start]:pl-4",
        icon: "size-9",
        "icon-xs": "size-7 [&_svg:not([class*='size-'])]:size-3.5",
        "icon-sm": "size-8",
        "icon-lg": "size-11 [&_svg:not([class*='size-'])]:size-5",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

function Button({
  className,
  variant = "default",
  size = "default",
  asChild = false,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean
  }) {
  const Comp = asChild ? Slot.Root : "button"

  return (
    <Comp
      data-slot="button"
      data-variant={variant}
      data-size={size}
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button, buttonVariants }
