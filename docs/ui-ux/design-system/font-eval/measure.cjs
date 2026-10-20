// Build a specimen of every candidate and measure, in real Chrome:
//  - how far stacked Vietnamese diacritics reach above / below the line box at
//    each size of the DevPath type scale (positive = sticks out of its line);
//  - width of a Vietnamese sentence at 16px, x-height;
//  - a screenshot per font.
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const { pathToFileURL } = require("url");

const dir = __dirname;
const faces = JSON.parse(fs.readFileSync(path.join(dir, "dl", "faces.json"), "utf8"));
const families = [...new Set(faces.map((f) => f.family))];

const SCALE = [
  ["display", 40, 48, 700],
  ["h1", 30, 38, 700],
  ["h2", 24, 32, 600],
  ["h3", 20, 28, 600],
  ["body", 16, 24, 400],
  ["body-sm", 14, 20, 400],
  ["caption", 12, 16, 500],
];
const TOP = "ẪỮỖỜỢẰẲẴẶỄỂẾỀẤẦẨ";
const BOTTOM = "gjpqyỵỹặợậộịụ";
const SENTENCE = "Chương trình chạy xong nhưng in ra khác kết quả mong đợi ở test thứ ba.";

const fontFace = faces
  .map((f) => {
    const w = f.weight.includes(" ") ? f.weight : f.weight;
    return `@font-face{font-family:"${f.family}";font-weight:${w};font-style:normal;font-display:block;src:url("dl/${f.file}") format("woff2");unicode-range:${f.unicodeRange};}`;
  })
  .join("\n");

const rows = families
  .map(
    (fam) => `<section data-fam="${fam}" style="font-family:'${fam}';padding:24px 32px;border-bottom:1px solid #e3eaee;background:#fff;color:#102029">
  <div style="font:600 12px/16px system-ui;color:#556670;letter-spacing:.06em;margin-bottom:8px">${fam.toUpperCase()}</div>
  <div style="font-size:40px;line-height:48px;font-weight:700;letter-spacing:-0.02em">Luồng điều khiển của Người học</div>
  <div style="font-size:30px;line-height:38px;font-weight:700;letter-spacing:-0.015em">Tiếng Việt có dấu hai tầng: ưở ẫ ữ ỗ ợ ặ ỵ</div>
  <div style="font-size:24px;line-height:32px;font-weight:600">Bài 4 · Vòng lặp for · Đúng 10/10 câu</div>
  <p style="font-size:16px;line-height:24px;max-width:640px;margin:8px 0">${SENTENCE} Vòng lặp for đi qua từng phần tử của một dãy, theo đúng thứ tự; người học xem lại kết quả từng test ngay khi chấm xong.</p>
  <div style="font-size:14px;line-height:20px">Đạt từ 80% · 10 câu · 15 phút · 1.250 XP · 499.000 ₫ · Lỗi khi chạy · Quá bộ nhớ</div>
  <div style="font-size:12px;line-height:16px;font-weight:500;color:#556670">Cập nhật 21/10/2026 · NGƯỜI HỌC MỚI · ĐĂNG KÝ</div>
</section>`
  )
  .join("\n");

const html = `<!doctype html><html lang="vi"><head><meta charset="utf-8"><style>${fontFace}
body{margin:0;background:#f8fafc}</style></head><body>${rows}</body></html>`;
fs.writeFileSync(path.join(dir, "specimen.html"), html);

(async () => {
  const browser = await chromium.launch({ channel: "chrome" });
  const page = await browser.newPage({ viewport: { width: 1100, height: 900 }, deviceScaleFactor: 1 });
  await page.goto(pathToFileURL(path.join(dir, "specimen.html")).href);
  await page.evaluate(async (fams) => {
    const loads = [];
    for (const f of fams) for (const w of [400, 500, 600, 700]) loads.push(document.fonts.load(`${w} 16px "${f}"`, "Ẫa"));
    await Promise.all(loads);
  }, families);
  const result = await page.evaluate(
    ({ fams, SCALE, TOP, BOTTOM, SENTENCE }) => {
      const c = document.createElement("canvas").getContext("2d");
      return fams.map((fam) => {
        const rows = SCALE.map(([name, size, lh, w]) => {
          c.font = `${w} ${size}px "${fam}"`;
          const t = c.measureText(TOP);
          const b = c.measureText(BOTTOM);
          const fA = t.fontBoundingBoxAscent, fD = t.fontBoundingBoxDescent;
          const half = (lh - (fA + fD)) / 2;
          return {
            name,
            over: +(t.actualBoundingBoxAscent - (fA + half)).toFixed(1),
            under: +(b.actualBoundingBoxDescent - (fD + half)).toFixed(1),
          };
        });
        c.font = `400 16px "${fam}"`;
        const width = c.measureText(SENTENCE).width;
        const x = c.measureText("x").actualBoundingBoxAscent / 16;
        c.font = `400 16px "${fam}"`;
        const fA = c.measureText("x").fontBoundingBoxAscent, fD = c.measureText("x").fontBoundingBoxDescent;
        return { fam, rows, width: +width.toFixed(0), perChar: +(width / SENTENCE.length).toFixed(2), xHeight: +x.toFixed(3), contentArea: +((fA + fD) / 16).toFixed(2), loaded: document.fonts.check(`400 16px "${fam}"`, "ẫ") };
      });
    },
    { fams: families, SCALE, TOP, BOTTOM, SENTENCE }
  );
  const kb = (fam) => (faces.filter((f) => f.family === fam).reduce((s, f) => s + f.bytes, 0) / 1024).toFixed(1);
  for (const r of result) {
    const worst = r.rows.reduce((a, x) => (x.over > a.over ? x : a));
    console.log(
      `${r.fam.padEnd(20)} ${kb(r.fam).padStart(6)} KB  16px câu=${r.width}px (${r.perChar}/ký tự)  x=${r.xHeight}  vùng nội dung=${r.contentArea}em  loaded=${r.loaded}`
    );
    console.log("   trồi trên (px): " + r.rows.map((x) => `${x.name} ${x.over}`).join(" · "));
    console.log("   trồi dưới (px): " + r.rows.map((x) => `${x.name} ${x.under}`).join(" · "));
  }
  fs.mkdirSync(path.join(dir, "shots"), { recursive: true });
  for (const fam of families) {
    const el = await page.$(`section[data-fam="${fam}"]`);
    await el.screenshot({ path: path.join(dir, "shots", `${fam.toLowerCase().replace(/\s+/g, "-")}.png`) });
  }
  fs.writeFileSync(path.join(dir, "result.json"), JSON.stringify(result, null, 2));
  await browser.close();
})();
