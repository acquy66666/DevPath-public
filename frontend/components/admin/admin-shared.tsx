"use client";

import { Search, type LucideIcon } from "lucide-react";
import { useState, type FormEvent } from "react";

import { UserAvatar } from "@/components/auth/user-avatar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { AdminPerson } from "@/lib/api/admin";
import { ROLE_LABELS } from "@/lib/auth/roles";

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
        className="h-9 min-w-0"
      />
      <Button type="submit" variant="outline" className="h-9">
        <Search aria-hidden />
        <span className="hidden sm:inline">Tìm</span>
      </Button>
    </form>
  );
}

export function ListSkeleton({ rows = 3, height = "h-24" }: { rows?: number; height?: string }) {
  return (
    <div className="space-y-3" aria-hidden>
      {Array.from({ length: rows }, (_, row) => (
        <div key={row} className={`${height} animate-pulse rounded-xl border bg-muted/40`} />
      ))}
    </div>
  );
}

export function EmptyState({
  icon: Icon,
  title,
  hint,
}: {
  icon: LucideIcon;
  title: string;
  hint: string;
}) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed px-4 py-12 text-center">
      <Icon className="size-8 text-muted-foreground" aria-hidden />
      <p className="font-medium">{title}</p>
      <p className="max-w-md text-sm text-muted-foreground">{hint}</p>
    </div>
  );
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
