// Close-up of the hard glyphs for every candidate, plus the dong sign measured
// against the digits (a price is "499.000 ₫").
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const { pathToFileURL } = require("url");

const dir = __dirname;
const faces = JSON.parse(fs.readFileSync(path.join(dir, "dl", "faces.json"), "utf8"));
const families = [...new Set(faces.map((f) => f.family))];
const fontFace = faces
  .map((f) => `@font-face{font-family:"${f.family}";font-weight:${f.weight};src:url("dl/${f.file}") format("woff2");unicode-range:${f.unicodeRange};font-display:block}`)
  .join("\n");
const rows = families
  .map(
    (fam) => `<div class="r" style="font-family:'${fam}'"><span class="n">${fam}</span><span class="g">Luồng Người Tiếng Việt ưở ẫ ữ ỗ ợ ặ ỵ Ỵ Ữ</span><span class="p">499.000 ₫</span></div>`
  )
  .join("");
const html = `<!doctype html><html lang="vi"><head><meta charset="utf-8"><style>${fontFace}
body{margin:0;padding:16px 24px;background:#fff;color:#102029}
.r{display:flex;align-items:baseline;gap:24px;padding:6px 0;border-bottom:1px solid #e3eaee}
.n{font:600 13px/1 system-ui;color:#556670;width:150px;flex:none}
.g{font-size:44px;line-height:64px;font-weight:600}
.p{font-size:14px;line-height:20px;font-weight:600}
</style></head><body>${rows}</body></html>`;
fs.writeFileSync(path.join(dir, "closeup.html"), html);

(async () => {
  const b = await chromium.launch({ channel: "chrome" });
  const p = await b.newPage({ viewport: { width: 1180, height: 640 }, deviceScaleFactor: 1 });
  await p.goto(pathToFileURL(path.join(dir, "closeup.html")).href);
  await p.evaluate(async (fams) => Promise.all(fams.flatMap((f) => [400, 600].map((w) => document.fonts.load(`${w} 16px "${f}"`, "Ẫa₫")))), families);
  const dong = await p.evaluate((fams) => {
    const c = document.createElement("canvas").getContext("2d");
    return fams.map((fam) => {
      c.font = `600 100px "${fam}"`;
      const d = c.measureText("₫"), z = c.measureText("0"), dd = c.measureText("đ");
      return `${fam.padEnd(20)} ₫ cao ${(d.actualBoundingBoxAscent + d.actualBoundingBoxDescent).toFixed(0)} / số 0 cao ${(z.actualBoundingBoxAscent).toFixed(0)} / đ cao ${(dd.actualBoundingBoxAscent).toFixed(0)}  → ₫:0 = ${((d.actualBoundingBoxAscent + d.actualBoundingBoxDescent) / z.actualBoundingBoxAscent).toFixed(2)}`;
    });
  }, families);
  console.log(dong.join("\n"));
  await p.screenshot({ path: path.join(dir, "shots", "closeup.png"), fullPage: true });
  await b.close();
})();
