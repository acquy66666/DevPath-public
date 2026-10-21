"use client";

import { useState, type ReactNode } from "react";

// Every variant sits in the same shell, so the static variant's JS is the
// baseline the others are measured against. "Phát lại" remounts the mascot:
// a reaction plays once per event, and a new event is a new mount.
export function Stage({ variant, children }: { variant: string; children: ReactNode }) {
  const [round, setRound] = useState(0);
  return (
    <section data-variant={variant} style={{ display: "grid", gap: 16, justifyItems: "start" }}>
      <h1 style={{ fontSize: 20, fontWeight: 600 }}>Spike Naomi · celebrate · {variant}</h1>
      <button
        type="button"
        data-testid="replay"
        onClick={() => setRound((r) => r + 1)}
        style={{ padding: "6px 14px", border: "1px solid currentColor", borderRadius: 8 }}
      >
        Phát lại
      </button>
      <div key={round} data-round={round} data-testid="mascot" style={{ paddingTop: 48 }}>
        {children}
      </div>
    </section>
  );
}
