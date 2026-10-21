// For Be Vietnam Pro (and Geist as the baseline), how far stacked diacritics
// reach past the line box at the current and the proposed line-heights.
// Capitals (Ẫ Ữ…) are the worst case; lowercase (ẫ ữ…) is what most text has.
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const { pathToFileURL } = require("url");

const dir = __dirname;
const faces = JSON.parse(fs.readFileSync(path.join(dir, "dl", "faces.json"), "utf8")).filter((f) =>
  ["Be Vietnam Pro","Geist","Lexend","Manrope","Nunito"].includes(f.family)
);
const css = faces
  .map((f) => `@font-face{font-family:"${f.family}";font-weight:${f.weight};src:url("dl/${f.file}") format("woff2");unicode-range:${f.unicodeRange}}`)
  .join("\n");
fs.writeFileSync(path.join(dir, "lh.html"), `<!doctype html><meta charset="utf-8"><style>${css}</style><p style="font-family:'Be Vietnam Pro'">Ẫ</p><p style="font-family:'Geist'">Ẫ</p>`);

// name, size, weight, current lh, proposed lh
const SCALE = [
  ["display", 40, 700, 48, 52],
  ["h1", 30, 700, 38, 40],
  ["h2", 24, 600, 32, 32],
  ["h3", 20, 600, 28, 28],
  ["title", 16, 600, 24, 24],
  ["body-lg", 18, 400, 30, 30],
  ["body", 16, 400, 24, 24],
  ["body-sm", 14, 400, 20, 22],
  ["caption", 12, 500, 16, 18],
];
const CAP = "ẪỮỖỜỢẰẲẴẶỄỂẾỀẤẦẨỞỠ";
const LOW = "ẫữỗờợằẳẵặễểếềấầẩởỡ";
const DESC = "gjpqyỵỹặợậộịụ";

(async () => {
  const b = await chromium.launch({ channel: "chrome" });
  const p = await b.newPage();
  await p.goto(pathToFileURL(path.join(dir, "lh.html")).href);
  await p.evaluate(() => Promise.all(["Be Vietnam Pro","Geist","Lexend","Manrope","Nunito"].flatMap((f) => [400, 500, 600, 700].map((w) => document.fonts.load(`${w} 16px "${f}"`, "Ẫa")))));
  const out = await p.evaluate(({ SCALE, CAP, LOW, DESC }) => {
    const c = document.createElement("canvas").getContext("2d");
    const rows = [];
    for (const fam of ["Geist","Be Vietnam Pro","Lexend","Manrope","Nunito"]) {
      for (const [name, size, w, cur, prop] of SCALE) {
        c.font = `${w} ${size * 10}px "${fam}"`; // measure at 10x for precision
        const cap = c.measureText(CAP), low = c.measureText(LOW), d = c.measureText(DESC);
        const fA = cap.fontBoundingBoxAscent / 10, fD = cap.fontBoundingBoxDescent / 10;
        const over = (lh, m) => +(m.actualBoundingBoxAscent / 10 - (fA + (lh - fA - fD) / 2)).toFixed(1);
        const under = (lh) => +(d.actualBoundingBoxDescent / 10 - (fD + (lh - fA - fD) / 2)).toFixed(1);
        rows.push({ fam, name, cur, prop, capCur: over(cur, cap), lowCur: over(cur, low), capProp: over(prop, cap), lowProp: over(prop, low), underProp: under(prop) });
      }
    }
    return rows;
  }, { SCALE, CAP, LOW, DESC });
  for (const r of out)
    console.log(
      `${r.fam.padEnd(15)} ${r.name.padEnd(8)} lh ${r.cur}→${r.prop}  hoa trồi ${String(r.capCur).padStart(5)}→${String(r.capProp).padStart(5)}  thường trồi ${String(r.lowCur).padStart(5)}→${String(r.lowProp).padStart(5)}  dưới ${r.underProp}`
    );
  await b.close();
})();
