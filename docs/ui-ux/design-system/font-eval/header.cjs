// The guest header below `sm` (components/layout/site-header.tsx), rebuilt with the
// same CSS values, measured at 360px for each candidate font.
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const { pathToFileURL } = require("url");

const dir = __dirname;
const faces = JSON.parse(fs.readFileSync(path.join(dir, "dl", "faces.json"), "utf8"));
const fams = ["Geist", "Lexend", "Manrope", "Be Vietnam Pro"];
const css = faces
  .filter((f) => fams.includes(f.family))
  .map((f) => `@font-face{font-family:"${f.family}";font-weight:${f.weight};src:url("dl/${f.file}") format("woff2");unicode-range:${f.unicodeRange};font-display:block}`)
  .join("\n");
const header = (fam) => `<div class="h" data-fam="${fam}" style="font-family:'${fam}'">
  <div class="l"><a class="logo">Dev<span>Path</span></a><a class="nav">Khóa học</a></div>
  <div class="r"><a class="btn ghost">Đăng nhập</a><a class="btn prim">Đăng ký</a></div>
</div>`;
fs.writeFileSync(
  path.join(dir, "header.html"),
  `<!doctype html><meta charset="utf-8"><style>${css}
body{margin:0;background:#fff;color:#102029}
.h{width:360px;box-sizing:border-box;height:64px;padding:0 16px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #e3eaee}
.l{display:flex;align-items:center;gap:10px}.r{display:flex;align-items:center;gap:4px}
.logo{font-size:20px;line-height:28px;font-weight:600;letter-spacing:-0.025em}.logo span{color:#556670}
.nav{font-size:15px;white-space:nowrap;color:#556670}
.btn{display:inline-flex;align-items:center;height:36px;border:1px solid transparent;border-radius:8px;font-size:12.8px;font-weight:500;white-space:nowrap}
.ghost{padding:0 8px}.prim{padding:0 12px;background:#007967;color:#fff}
</style>${fams.map(header).join("")}`
);
(async () => {
  const b = await chromium.launch({ channel: "chrome" });
  const p = await b.newPage({ viewport: { width: 360, height: 300 }, deviceScaleFactor: 2 });
  await p.goto(pathToFileURL(path.join(dir, "header.html")).href);
  await p.evaluate((fs_) => Promise.all(fs_.flatMap((f) => [400, 500, 600].map((w) => document.fonts.load(`${w} 16px "${f}"`, "Ẫa")))), fams);
  const r = await p.evaluate(() =>
    [...document.querySelectorAll(".h")].map((h) => {
      const l = h.querySelector(".l").getBoundingClientRect().width;
      const rr = h.querySelector(".r").getBoundingClientRect().width;
      return `${h.dataset.fam.padEnd(15)} trái ${l.toFixed(1)} + phải ${rr.toFixed(1)} + lề 32 = ${(l + rr + 32).toFixed(1)}px (dư ${(360 - l - rr - 32).toFixed(1)}px), scrollWidth ${h.scrollWidth}`;
    })
  );
  console.log(r.join("\n"));
  await p.screenshot({ path: path.join(dir, "shots", "header-360.png"), fullPage: true });
  await b.close();
})();
