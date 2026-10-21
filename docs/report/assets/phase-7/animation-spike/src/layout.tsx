import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./_gen/spike.css";

// Throwaway: run.cjs copies this folder into frontend/app/(spike)/spike-naomi,
// builds, measures, and deletes it again.
export const metadata: Metadata = { robots: { index: false, follow: false } };

const VARIANTS = ["static", "css", "mini", "motion"];

export default function SpikeLayout({ children }: { children: ReactNode }) {
  return (
    <main style={{ padding: 24, display: "grid", gap: 16 }}>
      <nav style={{ display: "flex", gap: 12 }}>
        {VARIANTS.map((v) => (
          <a key={v} href={`/spike-naomi/${v}`} style={{ textDecoration: "underline" }}>
            {v}
          </a>
        ))}
      </nav>
      {children}
    </main>
  );
}
