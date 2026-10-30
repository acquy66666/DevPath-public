"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { MobileNavButton } from "@/components/layout/header-buttons";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

import { isCurrent, NAV } from "./site-nav";

/** Below `md`, the site's sections fold into this menu. Loaded lazily by the header. */
export function MobileNav() {
  const pathname = usePathname();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <MobileNavButton />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-56">
        {NAV.map((item) => (
          <DropdownMenuItem key={item.href} asChild>
            <Link
              href={item.href}
              aria-current={isCurrent(pathname, item.href) ? "page" : undefined}
              className="min-h-10 text-base aria-[current=page]:bg-secondary aria-[current=page]:font-semibold aria-[current=page]:text-secondary-foreground"
            >
              {item.label}
            </Link>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
