import { Star } from "lucide-react";

import { cn } from "@/lib/utils";

const STARS = [1, 2, 3, 4, 5] as const;

/**
 * Five stars, filled up to `value`.
 *
 * Rounded to a whole star: half a star drawn with a clipped icon reads as an
 * unstyled one at small sizes, and the exact figure is written next to it
 * anyway. The accessible name carries the real number, so a screen reader is
 * never handed the rounded version.
 */
export function StarRating({
  value,
  className,
  starClassName,
}: {
  value: number;
  className?: string;
  starClassName?: string;
}) {
  const filled = Math.round(value);

  return (
    <span
      className={cn("inline-flex items-center gap-0.5", className)}
      role="img"
      aria-label={`${value.toFixed(1)} trên 5 sao`}
    >
      {STARS.map((star) => (
        <Star
          key={star}
          aria-hidden
          className={cn(
            "size-4",
            star <= filled
              ? "fill-amber-500 text-amber-500"
              : "text-muted-foreground/40",
            starClassName,
          )}
        />
      ))}
    </span>
  );
}

const RATING_LABELS: Record<number, string> = {
  1: "1 sao — rất tệ",
  2: "2 sao — chưa tốt",
  3: "3 sao — tạm ổn",
  4: "4 sao — tốt",
  5: "5 sao — rất tốt",
};

/**
 * The same five stars, but as a choice.
 *
 * Real radio inputs rather than buttons: a radio group is what this is, and
 * using one means arrow keys, tab order and "which one is chosen" all work
 * without being reimplemented. The inputs are hidden visually only -- the star
 * is the label, and focus draws a ring around it.
 */
export function StarRatingInput({
  value,
  onChange,
  disabled,
  name = "rating",
}: {
  value: number;
  onChange: (rating: number) => void;
  disabled?: boolean;
  name?: string;
}) {
  return (
    <fieldset disabled={disabled} className="min-w-0">
      <legend className="sr-only">Chấm điểm khóa học</legend>

      <div className="flex items-center gap-1">
        {STARS.map((star) => (
          <label
            key={star}
            title={RATING_LABELS[star]}
            className={cn(
              "cursor-pointer rounded p-0.5 transition-colors",
              "focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2",
              disabled && "cursor-not-allowed opacity-60",
            )}
          >
            <input
              type="radio"
              name={name}
              value={star}
              checked={value === star}
              onChange={() => onChange(star)}
              className="sr-only"
            />
            <span className="sr-only">{RATING_LABELS[star]}</span>
            <Star
              aria-hidden
              className={cn(
                "size-7 transition-colors",
                star <= value
                  ? "fill-amber-500 text-amber-500"
                  : "text-muted-foreground/40",
              )}
            />
          </label>
        ))}
      </div>
    </fieldset>
  );
}
