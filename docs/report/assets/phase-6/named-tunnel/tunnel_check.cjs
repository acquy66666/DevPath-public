// D1: the public pages of https://<DOMAIN> in a real Chrome, through Cloudflare
// and the named tunnel. No sign-in. The certificate must validate as it is
// (no ignoreHTTPSErrors): the visitor's browser sees Cloudflare's, not the
// self-signed one nginx serves inside the tunnel.
//
//   NODE_PATH=frontend/node_modules node docs/report/assets/phase-6/named-tunnel/tunnel_check.cjs \
//     devpath-01.me docs/report/assets/phase-6/named-tunnel
const fs = require("node:fs");
const path = require("node:path");
const tls = require("node:tls");
const { chromium } = require("@playwright/test");

const [domain, outDir] = process.argv.slice(2);
const site = `https://${domain}`;

function certificate() {
  return new Promise((resolve, reject) => {
    const socket = tls.connect({ host: domain, port: 443, servername: domain }, () => {
      const cert = socket.getPeerCertificate();
      resolve({
        authorized: socket.authorized,
        subject: cert.subject?.CN,
        issuer: `${cert.issuer?.O} / ${cert.issuer?.CN}`,
        validTo: cert.valid_to,
        altNames: cert.subjectaltname,
        protocol: socket.getProtocol(),
      });
      socket.end();
    });
    socket.on("error", reject);
  });
}

(async () => {
  console.log("certificate", JSON.stringify(await certificate()));

  const browser = await chromium.launch({ channel: "chrome" });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  const problems = [];
  page.on("console", (m) => {
    if (m.type() === "error" || m.type() === "warning") problems.push(`${m.type()}: ${m.text()}`);
  });
  page.on("pageerror", (e) => problems.push(`pageerror: ${e.message}`));
  const media = [];
  page.on("response", (r) => {
    if (r.url().startsWith(`${site}/devpath-media/`)) media.push(`${r.status()} ${r.url().slice(site.length)}`);
  });

  for (const [name, route] of [["home", "/"], ["catalogue", "/khoa-hoc"]]) {
    const response = await page.goto(`${site}${route}`, { waitUntil: "networkidle" });
    const headers = response.headers();
    console.log(
      `page ${route}: ${response.status()} via ${headers.server} cf-ray=${Boolean(headers["cf-ray"])}` +
        ` csp-report-only=${Boolean(headers["content-security-policy-report-only"])}` +
        ` title="${await page.title()}"`,
    );
    await page.screenshot({ path: path.join(outDir, `tunnel-${name}-1440.png`) });
  }

  const courses = await page.locator('a[href^="/khoa-hoc/"]').evaluateAll((links) =>
    [...new Set(links.map((a) => a.getAttribute("href")))],
  );
  console.log(`catalogue links: ${courses.length} ${courses.join(" ")}`);
  if (courses[0]) {
    const response = await page.goto(`${site}${courses[0]}`, { waitUntil: "networkidle" });
    console.log(`page ${courses[0]}: ${response.status()} h1="${await page.locator("h1").first().textContent()}"`);
    await page.screenshot({ path: path.join(outDir, "tunnel-course-1440.png") });
  }

  const ready = await page.evaluate(async () => {
    const r = await fetch("/api/v1/health/ready");
    return `${r.status} ${await r.text()}`;
  });
  console.log(`fetch /api/v1/health/ready from the page: ${ready}`);
  console.log(`media through the tunnel: ${media.length ? media.join(", ") : "none"}`);
  console.log(`console errors/warnings: ${problems.length}`);
  for (const p of problems) console.log(`  ${p.slice(0, 300)}`);
  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
