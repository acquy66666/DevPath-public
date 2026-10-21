import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { NaomiPreview } from "./preview";

export const metadata: Metadata = {
  title: "Naomi — xem trước",
  robots: { index: false, follow: false },
};

/**
 * Every mood of the mascot side by side, to check reactions and capture
 * evidence (docs/report/assets/phase-7/mascot/). Development only: a
 * production build answers 404 unless it was built with MASCOT_PREVIEW=1,
 * which the capture script does to measure the real bundle.
 */
export default function NaomiPreviewPage() {
  if (process.env.NODE_ENV === "production" && process.env.MASCOT_PREVIEW !== "1") notFound();
  return <NaomiPreview />;
}
