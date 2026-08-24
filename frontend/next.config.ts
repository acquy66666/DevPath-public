import type { NextConfig } from "next";

const pollIntervalMs = Number(process.env.WATCH_POLL_INTERVAL_MS);

const nextConfig: NextConfig = {
  // Traces the files the server actually reaches and writes a self-contained
  // bundle to .next/standalone. The production image copies that instead of a
  // full node_modules, which is what keeps it small and toolchain-free.
  output: "standalone",

  // Docker on Windows and macOS runs the Linux kernel in a VM, and filesystem
  // events do not cross that boundary -- Turbopack sees a mounted source tree
  // that never appears to change. Polling is the only way it notices edits.
  // Set by compose only; a native `npm run dev` gets real events and skips it.
  ...(pollIntervalMs > 0 ? { watchOptions: { pollIntervalMs } } : {}),
};

export default nextConfig;
