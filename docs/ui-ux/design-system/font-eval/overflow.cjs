// Public pages of the running app at 360/375/1440px: horizontal overflow, the
// elements sticking out, which font actually rendered, and screenshots.
// BASE defaults to the host `next dev` on :3100.
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const BASE = process.env.BASE || "http://localhost:3100";
const OUT = path.join(__dirname, "app-shots");
fs.mkdirSync(OUT, { recursive: true });

(async () => {
  const courses = await (await fetch("https://devpath-01.me/api/v1/courses?page_size=4")).json();
  const slug = courses.items?.[0]?.slug;
  const pages = ["/", "/khoa-hoc", `/khoa-hoc/${slug}`, "/dang-nhap", "/dang-ky", "/bang-xep-hang", "/chinh-sach-bao-mat", "/khong-co-trang-nay"];
  const browser = await chromium.launch({ channel: "chrome" });
  let bad = 0;
  for (const width of [360, 375, 1440]) {
    const ctx = await browser.newContext({ viewport: { width, height: 900 } });
    const page = await ctx.newPage();
    for (const url of pages) {
      const resp = await page.goto(BASE + url, { waitUntil: "networkidle", timeout: 120000 }).catch((e) => ({ status: () => String(e).slice(0, 60) }));
      await page.evaluate(() => document.fonts.ready);
      const r = await page.evaluate(() => {
        const vw = document.documentElement.clientWidth;
        const out = [];
        for (const el of document.querySelectorAll("body *")) {
          const b = el.getBoundingClientRect();
          if (b.width && b.right > vw + 0.5 && getComputedStyle(el).position !== "fixed") {
            let p = el.parentElement, clipped = false;
            while (p) { const o = getComputedStyle(p); if (/(hidden|clip|auto|scroll)/.test(o.overflowX) && p.getBoundingClientRect().right <= vw + 0.5) { clipped = true; break; } p = p.parentElement; }
            if (!clipped) out.push(`${el.tagName.toLowerCase()}.${String(el.className).split(" ").slice(0, 3).join(".")} right=${b.right.toFixed(0)} "${(el.textContent || "").trim().slice(0, 30)}"`);
          }
        }
        const fontOk = document.fonts.check('16px "Lexend"', "Người");
        const used = getComputedStyle(document.body).fontFamily;
        return { sw: document.documentElement.scrollWidth, vw, out: out.slice(0, 5), fontOk, used };
      });
      const status = typeof resp?.status === "function" ? resp.status() : "?";
      const over = r.sw > r.vw;
      bad += over;
      console.log(`${String(width).padStart(4)} ${url.padEnd(34).slice(0, 34)} ${status} sw=${r.sw}/${r.vw}${over ? " TRÀN" : ""} lexend=${r.fontOk}${r.out.length ? "\n      " + r.out.join("\n      ") : ""}`);
      const name = (url === "/" ? "trang-chu" : url.slice(1).replace(/\//g, "_")).slice(0, 40);
      if ((width === 360 && ["/", "/dang-nhap"].includes(url)) || (width === 1440 && (url === "/" || url.startsWith("/khoa-hoc/"))) || (width === 375 && url === "/khoa-hoc"))
        await page.screenshot({ path: path.join(OUT, `${name}-${width}.png`), fullPage: false });
    }
    await ctx.close();
  }
  console.log(`\n${bad} lượt xem tràn ngang`);
  await browser.close();
})();
