// Does `truncate` / `line-clamp` (overflow: hidden) cut the top of stacked
// capital diacritics? Rendered at DPR 2 for Geist and Be Vietnam Pro, with and
// without 2px block padding.
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const { pathToFileURL } = require("url");

const dir = __dirname;
const faces = JSON.parse(fs.readFileSync(path.join(dir, "dl", "faces.json"), "utf8")).filter((f) =>
  ["Be Vietnam Pro", "Geist"].includes(f.family)
);
const css = faces
  .map((f) => `@font-face{font-family:"${f.family}";font-weight:${f.weight};src:url("dl/${f.file}") format("woff2");unicode-range:${f.unicodeRange};font-display:block}`)
  .join("\n");
const TEXT = "Ứng dụng Ẩn Ở Ữ Ỗ Ẫ trong bài học";
const cell = (fam, size, lh, w, pad) =>
  `<div class="c"><div class="lbl">${fam} ${size}/${lh} ${pad ? "+2px" : ""}</div><div style="font-family:'${fam}';font-size:${size}px;line-height:${lh}px;font-weight:${w};overflow:hidden;white-space:nowrap;text-overflow:ellipsis;width:300px;background:#e7fbf6;${pad ? "padding-block:2px;" : ""}">${TEXT}</div></div>`;
let body = "";
for (const fam of ["Geist", "Be Vietnam Pro"])
  for (const [size, lh, w] of [[14, 20, 400], [16, 24, 600], [14, 22, 400]])
    body += cell(fam, size, lh, w, false) + cell(fam, size, lh, w, true);
fs.writeFileSync(
  path.join(dir, "clip.html"),
  `<!doctype html><meta charset="utf-8"><style>${css} body{margin:12px;font:12px system-ui;color:#102029;display:grid;grid-template-columns:repeat(2,340px);gap:10px}.lbl{color:#556670;margin-bottom:2px}</style>${body}`
);
(async () => {
  const b = await chromium.launch({ channel: "chrome" });
  const p = await b.newPage({ viewport: { width: 720, height: 420 }, deviceScaleFactor: 2 });
  await p.goto(pathToFileURL(path.join(dir, "clip.html")).href);
  await p.evaluate(() => Promise.all(["Be Vietnam Pro", "Geist"].flatMap((f) => [400, 600].map((w) => document.fonts.load(`${w} 16px "${f}"`, "Ẫa")))));
  await p.screenshot({ path: path.join(dir, "shots", "clip.png"), fullPage: true });
  await b.close();
})();
