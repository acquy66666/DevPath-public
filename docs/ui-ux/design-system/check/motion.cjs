// Click "Phát" on the Motion preview and read where each puck is, with and without reduced motion.
const { chromium } = require("playwright");
const path = require("path");
const { pathToFileURL } = require("url");

(async () => {
  const b = await chromium.launch({ channel: "chrome" });
  for (const rm of ["no-preference", "reduce"]) {
    const p = await b.newPage({ viewport: { width: 960, height: 420 }, reducedMotion: rm });
    await p.goto(pathToFileURL(path.join(__dirname, "out", "Motion.html")).href);
    await p.click("#mo-play");
    await p.waitForTimeout(80);
    const x = () => p.$$eval(".dp-puck", (els) => els.map((e) => Math.round(new DOMMatrix(getComputedStyle(e).transform).m41)));
    const mid = await x();
    await p.waitForTimeout(900);
    const end = await x();
    console.log(rm, "| at 80ms", mid.join(","), "| at 980ms", end.join(","), "|", await p.textContent("#mo-note"));
    if (rm === "no-preference") await p.screenshot({ path: path.join(__dirname, "shots", "Motion-run.png") });
    await p.close();
  }
  await b.close();
})();
