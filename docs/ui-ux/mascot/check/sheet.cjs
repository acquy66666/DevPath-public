// Contact sheet of every mascot SVG in a folder (default ../directions): each
// drawing at 200, 64 and 32 px plus its silhouette, on the page background of
// the design system.
//
//   NODE_PATH=frontend/node_modules node docs/ui-ux/mascot/check/sheet.cjs [filter] [--dir naomi/moods]
//
// --dir is relative to docs/ui-ux/mascot. Writes check/out/sheet[-dir][-filter].png.
// Chrome from the Playwright channel; no network, no app stack.
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const args = process.argv.slice(2);
const dirAt = args.indexOf("--dir");
const dirName = dirAt >= 0 ? args.splice(dirAt, 2)[1] : "directions";
const dir = path.join(__dirname, "..", dirName);
const out = path.join(__dirname, "out");
const filter = args[0] || "";

const files = fs
  .readdirSync(dir)
  .filter((f) => f.endsWith(".svg") && f.includes(filter))
  .sort();

const cell = (f) => {
  const src = "data:image/svg+xml;base64," + fs.readFileSync(path.join(dir, f)).toString("base64");
  return `<figure>
    <div class="row">
      <img src="${src}" width="200" height="200" alt="">
      <div class="small">
        <img src="${src}" width="64" height="64" alt="">
        <img src="${src}" width="32" height="32" alt="">
        <img src="${src}" width="64" height="64" alt="" class="sil">
      </div>
    </div>
    <figcaption>${f}</figcaption>
  </figure>`;
};

const html = `<!doctype html><meta charset="utf-8"><style>
  body { margin: 0; padding: 24px; background: #f8fafc; font: 13px system-ui; color: #102029;
         display: grid; grid-template-columns: repeat(4, 320px); gap: 16px; }
  figure { margin: 0; background: #fff; border: 1px solid #e3eaee; border-radius: 12px; padding: 12px; }
  .row { display: flex; gap: 12px; align-items: center; }
  .small { display: flex; flex-direction: column; gap: 8px; align-items: center; }
  .sil { filter: brightness(0); }
  figcaption { margin-top: 6px; color: #556670; }
</style>${files.map(cell).join("")}`;

(async () => {
  fs.mkdirSync(out, { recursive: true });
  const browser = await chromium.launch({ channel: "chrome" });
  const page = await browser.newPage({ viewport: { width: 1400, height: 400 }, deviceScaleFactor: Number(process.env.SCALE || 1) });
  await page.setContent(html);
  await page.waitForFunction(() => [...document.images].every((i) => i.complete));
  const slug = dirName === "directions" ? "" : "-" + dirName.replace(/[\/]+/g, "-");
  const file = path.join(out, `sheet${slug}${filter ? "-" + filter : ""}.png`);
  await page.screenshot({ path: file, fullPage: true });
  await browser.close();
  console.log(file, files.length, "drawings");
})();
