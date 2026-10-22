import * as React from "react"

import { fieldClass } from "@/components/ui/input"
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
        fieldClass,
        "h-10 appearance-none bg-[length:1rem] bg-[right:0.75rem_center] bg-no-repeat py-2 pr-9 pl-3",
        // The chevron, inline so it needs no network request. A data: URL
        // cannot read CSS variables, so it spells out `input` (slate-500).
        "bg-[url('data:image/svg+xml;charset=utf-8,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 fill=%22none%22 viewBox=%220 0 24 24%22 stroke-width=%222%22 stroke=%22%236f7e88%22%3E%3Cpath stroke-linecap=%22round%22 stroke-linejoin=%22round%22 d=%22m6 9 6 6 6-6%22/%3E%3C/svg%3E')]",
        className
      )}
      {...props}
    >
      {children}
    </select>
  )
}

export { NativeSelect }
