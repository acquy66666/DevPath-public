// Screenshot every built preview at 960px, report horizontal overflow and console errors.
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

(async () => {
  const out = path.join(__dirname, "out");
  const shots = path.join(__dirname, "shots");
  fs.mkdirSync(shots, { recursive: true });
  const browser = await chromium.launch({ channel: "chrome" });
  for (const width of [960, 400]) {
    const page = await browser.newPage({ viewport: { width, height: 600 } });
    const errors = [];
    page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
    page.on("pageerror", (e) => errors.push(String(e)));
    for (const f of fs.readdirSync(out).filter((n) => n.endsWith(".html"))) {
      errors.length = 0;
      await page.goto("file:///" + path.join(out, f).replace(/\\/g, "/"));
      await page.evaluate(() => document.fonts.ready);
      await page.waitForTimeout(300);
      const m = await page.evaluate(() => ({
        sw: document.documentElement.scrollWidth,
        cw: document.documentElement.clientWidth,
        h: document.documentElement.scrollHeight,
        font: getComputedStyle(document.body).fontFamily,
        lexend: document.fonts.check('16px "Lexend"'),
      }));
      const name = f.replace(".html", "");
      await page.screenshot({ path: path.join(shots, `${name}-${width}.png`), fullPage: true });
      console.log(`${width} ${name.padEnd(11)} h=${m.h} overflow=${m.sw > m.cw ? m.sw - m.cw : 0} lexend=${m.lexend} errors=${errors.length ? errors.join(" | ") : 0}`);
    }
    await page.close();
  }
  await browser.close();
})();
