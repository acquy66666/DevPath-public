// Small-size legibility at DPR 1 (an ordinary laptop screen): can a reader tell
// ẩ ẫ ấ ầ ậ apart at 12 and 14px? Screenshot is then scaled up 3x without smoothing.
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const { pathToFileURL } = require("url");

const dir = __dirname;
const faces = JSON.parse(fs.readFileSync(path.join(dir, "dl", "faces.json"), "utf8"));
const fams = ["Geist", "Manrope", "Lexend", "Be Vietnam Pro"];
const css = faces
  .filter((f) => fams.includes(f.family))
  .map((f) => `@font-face{font-family:"${f.family}";font-weight:${f.weight};src:url("dl/${f.file}") format("woff2");unicode-range:${f.unicodeRange};font-display:block}`)
  .join("\n");
const S = "ẩ ẫ ấ ầ ậ · ể ễ ế ề ệ · ổ ỗ ố ồ ộ · ử ữ ứ ừ ự · Cập nhật 21/10 · Người học";
const rows = fams
  .map((f) => `<div style="font-family:'${f}'"><span class="n">${f}</span><span style="font-size:12px;line-height:18px;font-weight:500">${S}</span><br><span class="n"></span><span style="font-size:14px;line-height:20px">${S}</span></div>`)
  .join("");
fs.writeFileSync(
  path.join(dir, "small.html"),
  `<!doctype html><meta charset="utf-8"><style>${css} body{margin:8px;color:#102029;background:#fff}div{margin-bottom:8px}.n{display:inline-block;width:110px;font:11px system-ui;color:#556670}</style>${rows}`
);
(async () => {
  const b = await chromium.launch({ channel: "chrome" });
  const p = await b.newPage({ viewport: { width: 560, height: 230 }, deviceScaleFactor: 1 });
  await p.goto(pathToFileURL(path.join(dir, "small.html")).href);
  await p.evaluate((fs_) => Promise.all(fs_.flatMap((f) => [400, 500].map((w) => document.fonts.load(`${w} 16px "${f}"`, "Ẫa")))), fams);
  const buf = await p.screenshot();
  // scale up 3x with nearest-neighbour so the pixels stay honest
  const q = await b.newPage({ viewport: { width: 1680, height: 690 } });
  await q.setContent(`<body style="margin:0"><img src="data:image/png;base64,${buf.toString("base64")}" style="width:1680px;image-rendering:pixelated"></body>`);
  await q.screenshot({ path: path.join(dir, "shots", "small-3x.png") });
  await b.close();
})();
