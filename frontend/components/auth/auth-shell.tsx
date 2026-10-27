import type { LucideIcon } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { Mascot } from "@/components/mascot/mascot";

export interface AuthPoint {
  icon: LucideIcon;
  text: string;
}

/**
 * The sign-in and sign-up card: on a wide screen, why to be here on the left
 * (Naomi waving, a heading, three points) and the form on the right; below
 * `lg` the form alone, with a small Naomi beside its title.
 *
 * Naomi is still: nothing has happened yet to react to. She is drawn twice --
 * the large one in the side panel, the small one in the form's header -- and
 * CSS shows exactly one, so every width has one Naomi.
 */
export function AuthShell({
  title,
  description,
  aside,
  children,
}: {
  title: string;
  description: ReactNode;
  aside: { heading: string; text: string; points: AuthPoint[] };
  children: ReactNode;
}) {
  return (
    <div className="w-full max-w-md overflow-hidden rounded-xl border bg-card shadow-md lg:grid lg:max-w-[65rem] lg:grid-cols-[minmax(0,1fr)_minmax(0,27.5rem)]">
      <section aria-label="DevPath" className="hidden flex-col gap-6 bg-secondary px-12 py-10 lg:flex">
        <Logo className="text-h3" />
        <Mascot mood="wave" className="mt-2 size-44" />
        <div className="space-y-2">
          <h2 className="text-h1 text-balance">{aside.heading}</h2>
          <p className="max-w-[30em] text-body text-foreground/80">{aside.text}</p>
        </div>
        <ul className="space-y-3 text-body text-foreground/80">
          {aside.points.map(({ icon: Icon, text }) => (
            <li key={text} className="flex items-center gap-2.5">
              <Icon className="size-4.5 shrink-0 text-primary" aria-hidden />
              {text}
            </li>
          ))}
        </ul>
      </section>

      <section className="flex min-w-0 flex-col gap-5 px-5 py-6 sm:px-6 lg:p-10">
        <div className="flex items-center gap-3">
          <Mascot mood="wave" className="size-18 rounded-lg bg-secondary lg:hidden" />
          <div className="min-w-0 space-y-0.5">
            <Logo className="text-body font-bold lg:hidden" />
            <h1 className="text-h2">{title}</h1>
          </div>
        </div>
        <p className="-mt-2 text-body text-muted-foreground lg:-mt-3">{description}</p>
        {children}
      </section>
    </div>
  );
}

function Logo({ className }: { className?: string }) {
  return (
    <Link
      href="/"
      aria-label="DevPath — về trang chủ"
      className={`w-fit font-bold tracking-tight text-foreground transition-opacity hover:opacity-70 ${className ?? ""}`}
    >
      Dev<span className="text-primary">Path</span>
    </Link>
  );
}
