"use client";

import { Flag } from "lucide-react";
import dynamic from "next/dynamic";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import type { ReportTargetType } from "@/lib/api/reports";
import { useAuth } from "@/lib/auth/auth-provider";
import { cn } from "@/lib/utils";

// The dialog and its form load on the first click (see report-dialog.tsx).
const ReportDialog = dynamic(() => import("./report-dialog").then((m) => m.ReportDialog), {
  ssr: false,
});

/**
 * "Báo cáo" under something a learner can see, and the form behind it.
 *
 * Draws nothing on the reader's own words -- the backend refuses those
 * (`CANNOT_REPORT_OWN_CONTENT`), and a button that exists to fail is worse than
 * none. A visitor who is not signed in gets the button too, and the dialog
 * says why it needs an account: reports are tied to a person so one person
 * cannot flood the queue.
 *
 * The dialog is mounted while open and unmounted on close, so every opening
 * starts from an empty form.
 */
export function ReportButton({
  targetType,
  targetId,
  authorId,
  className,
  label = "Báo cáo",
}: {
  targetType: ReportTargetType;
  targetId: string;
  /** Who wrote it; the button hides for them. */
  authorId?: string | null;
  className?: string;
  label?: string;
}) {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);

  if (user !== null && authorId && user.id === authorId) return null;

  return (
    <>
      <Button
        variant="ghost"
        size="sm"
        className={cn("h-7 gap-1 px-2 text-xs text-muted-foreground", className)}
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={() => setOpen(true)}
      >
        <Flag className="size-3.5" aria-hidden />
        {label}
      </Button>
      {open ? (
        <ReportDialog targetType={targetType} targetId={targetId} onClose={() => setOpen(false)} />
      ) : null}
    </>
  );
}
