/**
 * One Lighthouse run (mobile, simulated throttling, same route as measure.cjs)
 * with some URLs blocked: how much a group of files costs the simulated LCP.
 * Used for the Phase 7 performance task to find what to cut (performance.md §3).
 *
 *   cd <repo>   (stack demo up; Git Bash needs MSYS_NO_PATHCONV=1)
 *   MSYS_NO_PATHCONV=1 node docs/report/assets/phase-7/performance/probe.cjs / no-mono "*geist-mono*"
 *
 * Prints simulated LCP/FCP, the observed LCP, and the bytes Lighthouse saw
 * start before that observed LCP -- the ones its simulation counts.
 * Writes nothing to the repository (report in the system temp directory).
 */
const { execFileSync } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const [urlPath = "/", label = "probe", ...blocked] = process.argv.slice(2);
const base = process.env.BASE_URL ?? "https://devpath-01.me";
const host = new URL(base).host;
const out = path.join(os.tmpdir(), `devpath-probe-${label}.json`);
const win = process.platform === "win32";
const quote = (arg) => (win ? `"${arg}"` : arg);
const flags = `--headless --host-resolver-rules='MAP ${host} ${process.env.RESOLVE_TO ?? "127.0.0.1"}' --ignore-certificate-errors`;
const args = ["-y", "lighthouse@13.5.0", quote(`${base}${urlPath}`), quote(`--chrome-flags=${flags}`),
  "--only-categories=performance", "--output=json", quote(`--output-path=${out}`), "--quiet"];
for (const pattern of blocked) args.push(quote(`--blocked-url-patterns=${pattern}`));
execFileSync(win ? "npx.cmd" : "npx", args, { stdio: "ignore", shell: win });

const report = JSON.parse(fs.readFileSync(out, "utf8"));
const m = report.audits.metrics.details.items[0];
const early = report.audits["network-requests"].details.items.filter(
  (r) => r.networkRequestTime <= m.observedLargestContentfulPaint && r.statusCode > 0,
);
const kb = early.reduce((n, r) => n + r.transferSize, 0) / 1024;
console.log(label.padEnd(16), "LCP", Math.round(m.largestContentfulPaint), "FCP", Math.round(m.firstContentfulPaint),
  "observed LCP", m.observedLargestContentfulPaint, "| before it:", early.length, "requests,", kb.toFixed(0), "KB");
