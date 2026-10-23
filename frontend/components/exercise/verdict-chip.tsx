import {
  Check,
  Clock,
  CodeXml,
  Cpu,
  LoaderCircle,
  Wrench,
  X,
  Zap,
  type LucideIcon,
} from "lucide-react";

import {
  VERDICT_CLASSES,
  VERDICT_LABELS,
  asVerdict,
  type Verdict,
} from "@/lib/grading/verdicts";
import { cn } from "@/lib/utils";

/** One icon per letter (design system, component Verdict). */
export const VERDICT_ICONS: Record<Verdict, LucideIcon> = {
  AC: Check,
  WA: X,
  TLE: Clock,
  MLE: Cpu,
  RE: Zap,
  CE: CodeXml,
  SE: Wrench,
};

const CHIP =
  "inline-flex h-7 shrink-0 items-center gap-1.5 rounded-full px-3 text-[0.8125rem] leading-[1.125rem] font-semibold whitespace-nowrap [&_svg]:size-3.5 [&_svg]:shrink-0";

/**
 * A verdict as a chip: icon, the letter in mono, the words. Colour is never
 * the only signal -- the letter and the words say it too.
 *
 * `surface` is what it sits on: `soft` (the default) tints the chip itself, as
 * in the history list; `card` keeps it white for a chip laid on a band that is
 * already the verdict's colour.
 */
export function VerdictChip({
  verdict,
  surface = "soft",
  className,
}: {
  verdict: string;
  surface?: "soft" | "card";
  className?: string;
}) {
  const letter = asVerdict(verdict) ?? "SE";
  const Icon = VERDICT_ICONS[letter];
  const tone = VERDICT_CLASSES[letter];
  return (
    <span className={cn(CHIP, tone.text, surface === "soft" ? tone.soft : "bg-card", className)}>
      <Icon aria-hidden />
      <span className="font-mono">{letter}</span>
      <span>{VERDICT_LABELS[letter]}</span>
    </span>
  );
}

/** A run that has no letter yet. */
export function GradingChip({ className }: { className?: string }) {
  return (
    <span className={cn(CHIP, "border border-border-strong bg-card text-primary", className)}>
      <LoaderCircle className="motion-safe:animate-spin" aria-hidden />
      Đang chấm
    </span>
  );
}
