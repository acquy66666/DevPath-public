/**
 * axe-core in a Playwright page, held to the Phase 7 bar: no `critical` and
 * no `serious` violation. Shared by the accessibility sweep and the
 * keyboard-only golden flow.
 */
import { readFileSync } from "node:fs";

import type { Page } from "@playwright/test";

const AXE = readFileSync(require.resolve("axe-core/axe.min.js"), "utf8");

export interface Finding {
  where: string;
  rule: string;
  impact: string;
  targets: string[];
}

/** Violations that fail the bar, with (up to five of) the elements they were found on. */
export async function axe(page: Page, where: string): Promise<Finding[]> {
  // Next streams a page's metadata in after the body, so <title> can land a
  // moment after "load". Give it that moment; a title that never comes is
  // still reported (document-title).
  await page.waitForFunction(() => document.title !== "", null, { timeout: 5_000 }).catch(() => {});
  if (!(await page.evaluate(() => "axe" in window))) await page.addScriptTag({ content: AXE });
  const violations = await page.evaluate(async () => {
    type Result = { violations: { id: string; impact: string; nodes: { target: string[] }[] }[] };
    const runner = (window as unknown as { axe: { run: (...a: unknown[]) => Promise<Result> } }).axe;
    const result = await runner.run(document, { resultTypes: ["violations"] });
    return result.violations.map((v) => ({
      rule: v.id,
      impact: v.impact,
      targets: v.nodes.slice(0, 5).map((n) => n.target.join(" ")),
    }));
  });
  return violations
    .filter((v) => v.impact === "critical" || v.impact === "serious")
    .map((v) => ({ where, ...v }));
}

export function report(findings: Finding[]): string {
  return findings
    .map((f) => `${f.where}: ${f.rule} (${f.impact}) — ${f.targets.join(" | ")}`)
    .join("\n");
}
