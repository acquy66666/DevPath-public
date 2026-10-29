"use client";

import { Search } from "lucide-react";
import { useState, type FormEvent, type ReactNode } from "react";

import { UserAvatar } from "@/components/auth/user-avatar";
import { Button } from "@/components/ui/button";
import { EmptyState as SharedEmptyState, type EmptyMood } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Skeleton, SkeletonRegion, SkeletonText } from "@/components/ui/skeleton";
import type { AdminPerson } from "@/lib/api/admin";
import { ROLE_LABELS } from "@/lib/auth/roles";
import { cn } from "@/lib/utils";

/**
 * A search box that asks on Enter (or the button), not on every keystroke:
 * each query is a count and a page over a table the admin is scrolling, and
 * nobody reads the results of "Ng", "Ngu", "Nguy".
 */
export function SearchBox({
  id,
  placeholder,
  initial,
  onSearch,
}: {
  id: string;
  placeholder: string;
  initial: string;
  onSearch: (q: string) => void;
}) {
  const [value, setValue] = useState(initial);

  function submit(event: FormEvent) {
    event.preventDefault();
    onSearch(value.trim());
  }

  return (
    // The floor is what makes a phone wrap the filters beside it onto the
    // next line; at `min-w-0` the row kept them and squeezed this to a sliver.
    <form role="search" onSubmit={submit} className="flex min-w-[min(100%,16rem)] flex-1 gap-2">
      <label htmlFor={id} className="sr-only">
        Tìm kiếm
      </label>
      <Input
        id={id}
        type="search"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder={placeholder}
        maxLength={100}
        className="min-w-0"
      />
      <Button type="submit" variant="outline" className="h-10">
        <Search aria-hidden />
        <span className="max-sm:sr-only">Tìm</span>
      </Button>
    </form>
  );
}

/**
 * Rows on their way. `height` is the real row's (a queue card is `h-24`, a
 * table line `h-12`), so the list below the toolbar does not move when the
 * rows land.
 *
 * `fill` for a list that is usually longer than the screen (every account,
 * the dashboard, the catalogue settings): the skeleton then reserves the
 * screen, so the footer -- pinned to the bottom of a short page -- is not
 * shown and pushed away again when the rows land. Not for a queue that is
 * usually short or empty (courses to review, reports): there the reserved
 * room is what would move. Measured both ways on 22/10
 * (`docs/report/assets/phase-7/site-states.md`).
 */
export function ListSkeleton({
  rows = 3,
  height = "h-24",
  fill = false,
}: {
  rows?: number;
  height?: string;
  fill?: boolean;
}) {
  return (
    <SkeletonRegion label="Đang tải…" className={cn("space-y-3", fill && "min-h-[75dvh]")}>
      {Array.from({ length: rows }, (_, row) => (
        <Skeleton key={row} className={cn(height, "rounded-lg")} />
      ))}
    </SkeletonRegion>
  );
}

/**
 * The top of every admin screen: what it is called, one line on what it is
 * for, and the screen's own buttons on the right. The one `h1` of the page --
 * sections below it are `h2`.
 */
export function AdminTitle({
  id,
  title,
  description,
  actions,
}: {
  id?: string;
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0 space-y-1">
        <h1 id={id} className="text-h2 text-pretty sm:text-h1">
          {title}
        </h1>
        {description ? (
          <p className="max-w-3xl text-body text-pretty text-muted-foreground">{description}</p>
        ) : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  );
}

/**
 * An admin screen before anything is known: its title, a toolbar and rows.
 * The body of `quan-tri/loading.tsx`, and what `AdminGate` shows beside its
 * menu. Most admin screens are longer than one screen, so it reserves one
 * (`fill`).
 */
export function AdminBodySkeleton() {
  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <SkeletonText size="h1" className="h-8 w-64 max-w-full sm:h-10" />
        <SkeletonText className="w-full max-w-xl" />
      </div>
      <div className="space-y-3">
        <Skeleton className="h-10 w-80 max-w-full" />
        <ListSkeleton fill />
      </div>
    </div>
  );
}

/**
 * The admin menu before the session is known, in bars, since the visitor may
 * turn out not to be an admin: four groups beside the screen from `lg`, the
 * folded button below.
 */
export function AdminNavSkeleton() {
  return (
    <>
      <div className="-ml-3 hidden w-60 shrink-0 space-y-5 lg:block" aria-hidden>
        {[1, 3, 5, 3].map((rows, group) => (
          <div key={group} className="space-y-1">
            <Skeleton className="mx-3 mb-2.5 h-3 w-20" />
            {Array.from({ length: rows }, (_, row) => (
              <Skeleton key={row} className="h-10 rounded-md" />
            ))}
          </div>
        ))}
      </div>
      <Skeleton className="h-11 rounded-md lg:hidden" aria-hidden />
    </>
  );
}

/**
 * An admin list with nothing in it. Naomi sits beside the words at 80px: in
 * the admin area she only shows up here, and stays small (design doc §2).
 * `mood` picks her prop -- `empty-search` when a filter or a search found
 * nothing, `empty-courses` for a course queue.
 */
export function EmptyState({ mood = "empty", title, hint }: { mood?: EmptyMood; title: string; hint: string }) {
  return <SharedEmptyState mood={mood} size="md" title={title} description={hint} />;
}

/** Name, email and role of somebody an admin is about to act on. */
export function PersonLine({ person, label }: { person: AdminPerson; label?: string }) {
  return (
    <span className="flex min-w-0 items-center gap-2">
      <UserAvatar user={person} className="size-6 shrink-0 text-[0.6rem]" />
      <span className="min-w-0 truncate">
        {label ? <span className="text-muted-foreground">{label} </span> : null}
        <span className="font-medium">{person.full_name}</span>{" "}
        <span className="text-muted-foreground">
          · {person.email} · {ROLE_LABELS[person.role]}
        </span>
        {person.locked_at ? <span className="text-destructive"> · đã khóa</span> : null}
      </span>
    </span>
  );
}
