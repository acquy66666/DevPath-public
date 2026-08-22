import * as React from "react"

import { cn } from "@/lib/utils"

/**
 * A plain `<select>` wearing the same clothes as `<Input>`.
 *
 * shadcn's Select is a listbox built out of divs; this one is the browser's,
 * which already knows how to open on a phone, filter by typed letters and stay
 * reachable from the keyboard. For a list of categories that is the better
 * trade -- the custom widget earns its keep when options need icons or search.
 */
function NativeSelect({ className, children, ...props }: React.ComponentProps<"select">) {
  return (
    <select
      data-slot="native-select"
      className={cn(
        "h-8 w-full min-w-0 appearance-none rounded-lg border border-input bg-transparent bg-[length:1rem] bg-[right:0.5rem_center] bg-no-repeat px-2.5 py-1 pr-8 text-base transition-colors outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:pointer-events-none disabled:cursor-not-allowed disabled:bg-input/50 disabled:opacity-50 aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/20 md:text-sm dark:bg-input/30",
        // The chevron, inline so it needs no network request and follows the
        // current text colour in both themes.
        "bg-[url('data:image/svg+xml;charset=utf-8,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 fill=%22none%22 viewBox=%220 0 24 24%22 stroke-width=%222%22 stroke=%22%23888%22%3E%3Cpath stroke-linecap=%22round%22 stroke-linejoin=%22round%22 d=%22m6 9 6 6 6-6%22/%3E%3C/svg%3E')]",
        className
      )}
      {...props}
    >
      {children}
    </select>
  )
}

export { NativeSelect }
