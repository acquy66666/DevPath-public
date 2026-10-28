"use client";

import { cn } from "@/lib/utils";

/**
 * A row of toggle chips over an admin list, the same as the instructor's
 * course list. One is pressed; a count shows when it is known. Scrolls
 * sideways on a phone rather than wrapping into three lines.
 */
export function FilterChips<T extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: { value: T; label: string; count?: number }[];
  value: T;
  onChange: (value: T) => void;
}) {
  return (
    <div
      role="group"
      aria-label={label}
      className="relative -mx-4 flex gap-1.5 overflow-x-auto px-4 pb-0.5 sm:mx-0 sm:flex-wrap sm:px-0"
    >
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={value === option.value}
          onClick={() => onChange(option.value)}
          className={cn(
            "inline-flex h-9 shrink-0 items-center gap-1.5 rounded-full border px-3.5 text-body-sm whitespace-nowrap transition-colors duration-fast",
            value === option.value
              ? "border-primary bg-secondary font-semibold text-secondary-foreground"
              : "border-border-strong bg-card text-muted-foreground hover:bg-accent hover:text-foreground",
          )}
        >
          {option.label}
          {option.count !== undefined ? <span className="tabular-nums">· {option.count}</span> : null}
        </button>
      ))}
    </div>
  );
}
