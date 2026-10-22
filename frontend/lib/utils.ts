import { clsx, type ClassValue } from "clsx"
import { extendTailwindMerge } from "tailwind-merge"

import { MERGE_CONFIG } from "@/lib/design/tokens"

// Taught the design system's own names (text-body-sm, ease-standard,
// duration-fast), so a later class of the same kind wins and one of another
// kind survives. Plain twMerge reads `text-body-sm` as a colour and drops it
// next to `text-muted-foreground`.
const twMerge = extendTailwindMerge(MERGE_CONFIG)

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
