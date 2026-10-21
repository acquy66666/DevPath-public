// Render the canvas artboards (../canvas/project/*.dc.html) the way they are
// drawn on the artifact, but entirely offline: /_blob/<id> is answered with the
// SVG from ../directions (map in ../canvas/assets.json), Google Fonts with the
// self-hosted Lexend of the frontend, support.js with nothing (the boards hold
// no {{holes}}, so the runtime adds nothing to what is checked here).
//
//   NODE_PATH=frontend/node_modules node docs/ui-ux/mascot/check/boards.cjs [outDir]
//
// Prints, per board, whether its content fits the frame from canvas.json and
// which elements overflow sideways; exits 1 if any does not fit.
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const repo = path.join(__dirname, "..", "..", "..", "..");
const canvas = path.join(__dirname, "..", "canvas");
const project = path.join(canvas, "project");
const directions = path.join(__dirname, "..", "directions");
const fontsDir = path.join(repo, "frontend", "public", "fonts");
const outDir = path.resolve(process.argv[2] || path.join(__dirname, "out", "boards"));

const index = JSON.parse(fs.readFileSync(path.join(project, "canvas.json"), "utf8"));
const assets = JSON.parse(fs.readFileSync(path.join(canvas, "assets.json"), "utf8")).assets;

// Lexend + Geist Mono faces exactly as the app declares them, pointed at a fake host.
const fontCss = (fs.readFileSync(path.join(repo, "frontend", "app", "fonts.css"), "utf8").match(/@font-face\s*{[^}]*}/g) || [])
  .filter((block) => /font-family:\s*"(Lexend|Geist Mono)"/.test(block))
  .map((block) => block.replace(/url\("\/fonts\//g, 'url("https://fonts.local/'))
  .join("\n");

(async () => {
  fs.mkdirSync(outDir, { recursive: true });
  const browser = await chromium.launch({ channel: "chrome" });
  let failed = 0;
  for (const name of index.order) {
    const { w, h } = index.boards[name];
    const page = await browser.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 1 });
    await page.route("**/*", (route) => {
      const url = route.request().url();
      const blob = url.match(/\/_blob\/([0-9a-f]{32})/);
      if (blob) {
        return route.fulfill({ contentType: "image/svg+xml", body: fs.readFileSync(path.join(directions, assets[blob[1]])) });
      }
      if (url.startsWith("https://fonts.googleapis.com/")) return route.fulfill({ contentType: "text/css", body: fontCss });
      if (url.startsWith("https://fonts.local/")) {
        return route.fulfill({ contentType: "font/woff2", body: fs.readFileSync(path.join(fontsDir, url.slice(20))) });
      }
      if (url.endsWith("/support.js")) return route.fulfill({ contentType: "text/javascript", body: "" });
      if (url.startsWith("file:")) return route.continue();
      return route.abort();
    });
    await page.goto("file:///" + path.join(project, name).replace(/\\/g, "/"));
    await page.evaluate(() => document.fonts.ready);
    await page.waitForFunction(() => [...document.images].every((i) => i.complete && i.naturalWidth > 0));
    const report = await page.evaluate(() => {
      const root = document.querySelector("x-dc > div");
      const overflowing = [...root.querySelectorAll("*")]
        .filter((el) => el.scrollWidth > el.clientWidth + 1 && getComputedStyle(el).overflowX === "visible")
        .map((el) => `${el.tagName.toLowerCase()} "${(el.textContent || "").trim().slice(0, 40)}"`);
      const lexend = document.fonts.check('16px "Lexend"', "Tiếng Việt");
      return { content: root.scrollHeight, frame: root.clientHeight, overflowing, lexend };
    });
    const fits = report.content <= report.frame && report.overflowing.length === 0 && report.lexend;
    if (!fits) failed++;
    console.log(
      `${fits ? "ok  " : "FAIL"} ${name.padEnd(16)} frame ${w}x${h}, content height ${report.content}` +
        (report.overflowing.length ? `, overflow: ${report.overflowing.join("; ")}` : "") +
        (report.lexend ? "" : ", Lexend not loaded")
    );
    await page.screenshot({ path: path.join(outDir, name.replace(".dc.html", ".png")) });
    await page.close();
  }
  await browser.close();
  process.exit(failed ? 1 : 0);
})();
