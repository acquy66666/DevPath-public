// A real Chrome uploading to the production stack's bucket, the way the
// course editor does: `fetch(PUT)` of a file-sized Blob to a presigned URL on
// the page's own origin -- over HTTP/2, which a browser negotiates with nginx
// and the Python smoke test does not. Then reads it back as <video> would.
//
//   NODE_PATH=frontend/node_modules node browser-upload.cjs <presigned PUT url> <public url> <MB>
//
// Run on the host; Chrome sends *.localhost to 127.0.0.1 by itself, where the
// stack's nginx listens. The certificate is the drill's self-signed one.
const { chromium } = require("playwright");

(async () => {
  const [putUrl, publicUrl, megabytes] = process.argv.slice(2);
  const browser = await chromium.launch({ channel: "chrome" });
  const context = await browser.newContext({ ignoreHTTPSErrors: true });
  const page = await context.newPage();
  await page.goto(new URL("/", putUrl).href);

  const result = await page.evaluate(
    async ({ putUrl, publicUrl, megabytes }) => {
      const body = new Blob([new Uint8Array(megabytes * 1024 * 1024).fill(7)], { type: "video/mp4" });
      const started = performance.now();
      const put = await fetch(putUrl, { method: "PUT", body, headers: { "Content-Type": "video/mp4" } });
      const seconds = (performance.now() - started) / 1000;
      const got = await fetch(publicUrl, { headers: { Range: "bytes=0-15" } });
      const entries = performance.getEntriesByType("resource").filter((e) => e.name.includes("/devpath-media/"));
      return {
        put: put.status,
        seconds: seconds.toFixed(1),
        range: got.status,
        rangeBytes: (await got.arrayBuffer()).byteLength,
        protocols: [...new Set(entries.map((e) => e.nextHopProtocol))],
        page: performance.getEntriesByType("navigation")[0].nextHopProtocol,
      };
    },
    { putUrl, publicUrl, megabytes: Number(megabytes) },
  );
  console.log(JSON.stringify(result));
  await browser.close();
  process.exit(result.put === 200 && result.range === 206 ? 0 : 1);
})();
