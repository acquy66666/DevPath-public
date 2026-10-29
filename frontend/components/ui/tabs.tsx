"use client"

import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { Tabs as TabsPrimitive } from "radix-ui"

import { cn } from "@/lib/utils"

// Design system, component Tabs. Two looks, chosen on the list:
// - `tray` (default): a `muted` tray, the chosen tab lifted onto `card`. For
//   two to four short parts of one place ("Ghi chú | Hỏi đáp").
// - `line`: a rule under the row, the chosen tab underlined in `primary`. For
//   tabs that filter a whole page. A row longer than its box scrolls inside
//   itself instead of widening the page.
// Every TabsTrigger needs its TabsContent: a trigger whose panel is missing is
// the axe "critical" measured on the leaderboard before Phase 7.

//
// Motion (components/Motion: tab = duration-base): the `line` bar grows from
// the middle of the chosen tab, and a panel the reader switches to fades in
// rising 4px. The first panel does not: it is part of the page, and a fade on
// load would only hold back the first paint. With reduced motion the bar
// simply appears and the panel only fades.

function Tabs({
  className,
  onValueChange,
  ...props
}: React.ComponentProps<typeof TabsPrimitive.Root>) {
  const [switched, setSwitched] = React.useState(false)

  return (
    <TabsPrimitive.Root
      data-slot="tabs"
      data-switched={switched ? "" : undefined}
      className={cn("group/tabs flex flex-col gap-3", className)}
      onValueChange={(value) => {
        setSwitched(true)
        onValueChange?.(value)
      }}
      {...props}
    />
  )
}

const tabsListVariants = cva("group/tabs-list text-muted-foreground", {
  variants: {
    variant: {
      tray: "inline-flex h-10 w-fit items-center justify-center gap-0.5 rounded-md bg-muted p-1",
      // The rule is an inset shadow, not a border: the chosen tab's 2px bar
      // sits on top of it, and a scrolling row would clip anything below.
      line: "flex w-full max-w-full items-end gap-4 overflow-x-auto shadow-[inset_0_-1px_0_var(--color-border)] [scrollbar-width:thin]",
    },
  },
  defaultVariants: {
    variant: "tray",
  },
})

function TabsList({
  className,
  variant = "tray",
  ...props
}: React.ComponentProps<typeof TabsPrimitive.List> &
  VariantProps<typeof tabsListVariants>) {
  return (
    <TabsPrimitive.List
      data-slot="tabs-list"
      data-variant={variant}
      className={cn(tabsListVariants({ variant }), className)}
      {...props}
    />
  )
}

function TabsTrigger({
  className,
  ...props
}: React.ComponentProps<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      data-slot="tabs-trigger"
      className={cn(
        "relative inline-flex items-center justify-center gap-1.5 text-sm font-semibold whitespace-nowrap text-muted-foreground transition-[color,background-color,box-shadow] duration-base ease-standard hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50 data-[state=active]:text-foreground [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
        // tray
        "group-data-[variant=tray]/tabs-list:h-8 group-data-[variant=tray]/tabs-list:flex-1 group-data-[variant=tray]/tabs-list:rounded-sm group-data-[variant=tray]/tabs-list:px-3 group-data-[variant=tray]/tabs-list:data-[state=active]:bg-card group-data-[variant=tray]/tabs-list:data-[state=active]:shadow-sm",
        // line
        "group-data-[variant=line]/tabs-list:h-10 group-data-[variant=line]/tabs-list:shrink-0 group-data-[variant=line]/tabs-list:px-0.5 group-data-[variant=line]/tabs-list:after:absolute group-data-[variant=line]/tabs-list:after:inset-x-0 group-data-[variant=line]/tabs-list:after:bottom-0 group-data-[variant=line]/tabs-list:after:h-0.5 group-data-[variant=line]/tabs-list:after:rounded-full group-data-[variant=line]/tabs-list:after:bg-primary group-data-[variant=line]/tabs-list:after:scale-x-0 group-data-[variant=line]/tabs-list:data-[state=active]:after:scale-x-100 group-data-[variant=line]/tabs-list:after:transition-transform group-data-[variant=line]/tabs-list:after:duration-base group-data-[variant=line]/tabs-list:after:ease-standard motion-reduce:group-data-[variant=line]/tabs-list:after:transition-none",
        className
      )}
      {...props}
    />
  )
}

function TabsContent({
  className,
  ...props
}: React.ComponentProps<typeof TabsPrimitive.Content>) {
  return (
    <TabsPrimitive.Content
      data-slot="tabs-content"
      className={cn(
        "flex-1 group-data-switched/tabs:data-[state=active]:animate-in group-data-switched/tabs:data-[state=active]:fade-in-0 group-data-switched/tabs:data-[state=active]:duration-base group-data-switched/tabs:data-[state=active]:ease-enter motion-safe:group-data-switched/tabs:data-[state=active]:slide-in-from-bottom-1",
        className
      )}
      {...props}
    />
  )
}

export { Tabs, TabsList, TabsTrigger, TabsContent, tabsListVariants }
