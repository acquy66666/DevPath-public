import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

// Design system, component Alert: one message in the flow of the page, and
// what to do next. The tone is in the soft background and the icon, never a
// coloured left border.
const alertVariants = cva(
  "group/alert relative grid w-full gap-0.5 rounded-md px-4 py-3 text-left text-sm has-data-[slot=alert-action]:relative has-data-[slot=alert-action]:pr-18 has-[>svg]:grid-cols-[auto_1fr] has-[>svg]:gap-x-3 *:[svg]:row-span-2 *:[svg]:translate-y-px *:[svg:not([class*='size-'])]:size-4.5",
  {
    variants: {
      variant: {
        default: "border bg-card text-card-foreground *:[svg]:text-muted-foreground",
        info: "bg-info-soft text-info-text *:[svg]:text-info",
        success: "bg-success-soft text-success-text *:[svg]:text-success",
        warning: "bg-warning-soft text-warning-text *:[svg]:text-warning",
        destructive: "bg-destructive-soft text-destructive-text *:[svg]:text-destructive",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

/**
 * `role="alert"` interrupts a screen reader, so only an error gets it by
 * default -- the one just caused by what the user did. Everything else is a
 * polite `status`. Pass `role` to say otherwise.
 */
function Alert({
  className,
  variant,
  role,
  ...props
}: React.ComponentProps<"div"> & VariantProps<typeof alertVariants>) {
  return (
    <div
      data-slot="alert"
      data-variant={variant ?? "default"}
      role={role ?? (variant === "destructive" ? "alert" : "status")}
      className={cn(alertVariants({ variant }), className)}
      {...props}
    />
  )
}

function AlertTitle({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="alert-title"
      className={cn(
        "font-semibold group-has-[>svg]/alert:col-start-2 [&_a]:underline [&_a]:underline-offset-3",
        className
      )}
      {...props}
    />
  )
}

function AlertDescription({
  className,
  ...props
}: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="alert-description"
      className={cn(
        "text-sm text-pretty group-has-[>svg]/alert:col-start-2 [&_a]:underline [&_a]:underline-offset-3 [&_p:not(:last-child)]:mb-4",
        className
      )}
      {...props}
    />
  )
}

function AlertAction({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="alert-action"
      className={cn("absolute top-2 right-2", className)}
      {...props}
    />
  )
}

export { Alert, AlertTitle, AlertDescription, AlertAction }
