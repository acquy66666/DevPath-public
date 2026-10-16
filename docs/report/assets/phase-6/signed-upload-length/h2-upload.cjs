// A real Chrome uploading the way frontend/lib/api/storage.ts does -- an XHR
// PUT of a Blob, Content-Type set, Content-Length left to the browser -- to
// the URLs tickets.py signed, over HTTP/2 on the page's own origin.
//
//   NODE_PATH=frontend/node_modules node h2-upload.cjs <cases.json>
//
// Run on the host by run.sh: Chrome sends *.localhost to 127.0.0.1 by itself,
// where run.sh's nginx listens. The certificate is self-signed.
const fs = require("fs");
const { chromium } = require("playwright");

(async () => {
  const cases = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
  const browser = await chromium.launch({ channel: "chrome" });
  const context = await browser.newContext({ ignoreHTTPSErrors: true });
  const page = await context.newPage();
  await page.goto("https://devpath.localhost/");

  let surprises = 0;
  for (const item of cases) {
    const result = await page.evaluate(
      ({ url, bytes }) =>
        new Promise((resolve) => {
          const body = new Blob([new Uint8Array(bytes).fill(7)], { type: "video/mp4" });
          const request = new XMLHttpRequest();
          const started = performance.now();
          request.open("PUT", url, true);
          request.setRequestHeader("Content-Type", "video/mp4");
          request.addEventListener("loadend", () => {
            const entry = performance
              .getEntriesByType("resource")
              .filter((e) => e.name === url)
              .pop();
            resolve({
              status: request.status,
              seconds: ((performance.now() - started) / 1000).toFixed(2),
              protocol: entry ? entry.nextHopProtocol : "?",
            });
          });
          request.send(body);
        }),
      item,
    );
    const ok = result.status === item.expect;
    surprises += ok ? 0 : 1;
    const signed = item.signed === null ? "unsigned" : `signed ${item.signed}`;
    console.log(
      `${ok ? "PASS" : "FAIL"}  ${item.label.padEnd(34)} ${signed.padEnd(16)} ` +
        `body ${String(item.bytes).padStart(9)} B -> HTTP ${result.status} over ${result.protocol} (${result.seconds} s)`,
    );
  }
  await browser.close();
  process.exit(surprises ? 1 : 0);
})();
