import type { ReactNode } from "react";

/**
 * The admin area's frame: the side menu and the screen side by side from
 * `lg`, stacked below with the menu folded. Shared by the layout and by the
 * gate's skeleton, so nothing moves when the session is known.
 */
export function AdminFrame({ children }: { children: ReactNode }) {
  return (
    <div className="mx-auto max-w-6xl space-y-6 px-4 py-6 lg:flex lg:items-start lg:gap-8 lg:space-y-0 lg:py-10">
      {children}
    </div>
  );
}
