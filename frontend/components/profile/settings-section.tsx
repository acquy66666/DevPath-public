import type { ReactNode } from "react";

/**
 * One block of the profile's settings: what it is and what changing it does
 * on the left, the form on the right (stacked below `md`). A hairline above
 * separates the blocks, so the forms read as a list rather than a pile of
 * cards.
 */
export function SettingsSection({
  id,
  title,
  description,
  children,
}: {
  id: string;
  title: string;
  description?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section
      aria-labelledby={id}
      className="grid gap-3 border-t pt-6 md:grid-cols-[17.5rem_minmax(0,1fr)] md:gap-8"
    >
      <div className="space-y-1.5 md:pt-1">
        <h2 id={id} className="text-title">
          {title}
        </h2>
        {description ? <p className="text-body-sm text-muted-foreground">{description}</p> : null}
      </div>
      <div className="min-w-0 rounded-lg border bg-card p-5 md:p-6">{children}</div>
    </section>
  );
}
