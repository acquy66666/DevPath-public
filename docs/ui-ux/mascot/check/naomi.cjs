// Checks every drawing of Naomi (../naomi/views, ../naomi/moods) against the
// rules in ../README.md and exits 1 if one breaks:
//
//   1. every colour is a design-system token (tokens.json), no <style>, <text>,
//      <image> or url(#…) (an uploaded SVG loses <style>; an <img> has no fonts);
//   2. the named layers the animation component drives are all there, ids unique;
//   3. turmeric never paints her body: mouth, hands, feet, tail, head, body.
//      It is allowed in the eyes (iris), in props, effects and things she holds;
//   4. every colour on her body is at least MIN_DUO_DE (OKLab) from every Duo colour;
//   5. nothing is drawn outside the 200 × 200 frame;
//   6. the tail coil, the head spots and the tail spots are visible in every
//      drawing, and the body spots in the three views: share of the group's own
//      pixels that are not covered by something drawn on top of it.
//
//   NODE_PATH=frontend/node_modules node docs/ui-ux/mascot/check/naomi.cjs [report.txt]
//
// Chrome from the Playwright channel; no network.
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const mascot = path.join(__dirname, "..");
const repo = path.join(mascot, "..", "..", "..");
const tokens = JSON.parse(fs.readFileSync(path.join(repo, "docs/ui-ux/design-system/project/tokens.json"), "utf8")).color.tokens;
const tokenOf = Object.fromEntries(tokens.filter((t) => /^#[0-9a-f]{6}$/i.test(t.value)).map((t) => [t.value.toLowerCase(), t.name]));

// design.duolingo.com › Identity › Color, read 21/10/2026 (same values as duo_distance.py).
const DUO = { "Feather Green": "#58cc02", "Mask Green": "#89e219", "Wing Overlay": "#43c000", "Beak Upper": "#ffc200", "Beak Lower/Feet": "#f49000" };
const MIN_DUO_DE = 0.1;
const REQUIRED = ["shadow", "scene", "naomi", "fx-back", "tail", "tail-spots", "feet", "body", "body-spots", "props", "arm-right", "arm-left", "head", "head-shape", "head-spots", "eyes", "eyelids", "mouth", "props-head", "fx"];
// Parts of her own body: turmeric and Duo-like colours are not allowed here.
const BODY = ["mouth", "feet", "tail", "body", "head", "arm-right", "arm-left"];
const VISIBLE = { tail: 0.6, "head-spots": 0.5, "tail-spots": 0.5 };
const VISIBLE_IN_VIEWS = { "body-spots": 0.5 };

function oklab(hex) {
  const lin = (c) => ((c /= 255) <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  const [r, g, b] = [1, 3, 5].map((i) => lin(parseInt(hex.slice(i, i + 2), 16)));
  const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
  const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
  const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
  return [0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s, 1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s, 0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s];
}
const dE = (a, b) => Math.hypot(...oklab(a).map((v, i) => v - oklab(b)[i]));
const nearestDuo = (hex) => Object.entries(DUO).map(([name, v]) => ({ name, de: dE(hex, v) })).sort((a, b) => a.de - b.de)[0];

// Runs in the page: structure, colours by layer, overflow and visibility.
async function analyse({ svgText, groups }) {
  const parse = (t) => new DOMParser().parseFromString(t, "image/svg+xml");
  const ser = (d) => new XMLSerializer().serializeToString(d);
  const S = 2; // px per unit
  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  async function pixels(text, size) {
    canvas.width = canvas.height = size;
    ctx.clearRect(0, 0, size, size);
    const img = new Image();
    img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(text);
    await img.decode();
    ctx.drawImage(img, 0, 0, size, size);
    return ctx.getImageData(0, 0, size, size).data;
  }
  const doc = parse(svgText);
  const root = doc.documentElement;
  const all = [...root.querySelectorAll("*")];
  const ids = all.map((e) => e.id).filter(Boolean);
  const colours = [];
  for (const e of [root, ...all]) {
    for (const attr of ["fill", "stroke"]) {
      const v = (e.getAttribute(attr) || "").toLowerCase();
      if (!v || v === "none") continue;
      const chain = [];
      for (let n = e; n && n.nodeType === 1; n = n.parentNode) if (n.id) chain.push(n.id);
      colours.push({ value: v, chain });
    }
  }
  const banned = ["style", "text", "image", "foreignObject", "script"].filter((t) => doc.getElementsByTagName(t).length);
  const urlRefs = /url\(#/.test(svgText);

  // Overflow: draw with 20 units of margin on every side, count anything outside.
  const wide = parse(svgText);
  wide.documentElement.setAttribute("viewBox", "-20 -20 240 240");
  const px = await pixels(ser(wide), 240 * S);
  let overflow = 0;
  const sides = new Set();
  for (let y = 0; y < 240 * S; y++)
    for (let x = 0; x < 240 * S; x++) {
      const inside = x >= 20 * S && x < 220 * S && y >= 20 * S && y < 220 * S;
      if (!inside && px[(y * 240 * S + x) * 4 + 3] > 32) {
        overflow++;
        sides.add(y < 20 * S ? "trên" : y >= 220 * S ? "dưới" : x < 20 * S ? "trái" : "phải");
      }
    }

  // Visibility: the group painted magenta, once in the full drawing, once alone.
  const magenta = (d, id) => {
    const t = d.getElementById(id);
    if (!t) return null;
    for (const e of [t, ...t.querySelectorAll("*")])
      for (const attr of ["fill", "stroke"]) {
        const v = e.getAttribute(attr);
        if (v && v !== "none") e.setAttribute(attr, "#ff00ff");
      }
    return t;
  };
  const count = (data) => {
    let n = 0;
    for (let i = 0; i < data.length; i += 4) if (data[i] > 200 && data[i + 1] < 60 && data[i + 2] > 200 && data[i + 3] > 200) n++;
    return n;
  };
  const visible = {};
  for (const id of groups) {
    const full = parse(svgText);
    if (!magenta(full, id)) {
      visible[id] = null;
      continue;
    }
    const alone = parse(svgText);
    let node = magenta(alone, id);
    while (node.parentNode && node.parentNode.nodeType === 1) {
      for (const sib of node.parentNode.children) if (sib !== node) sib.setAttribute("display", "none");
      node = node.parentNode;
    }
    const a = count(await pixels(ser(alone), 200 * S));
    const f = count(await pixels(ser(full), 200 * S));
    visible[id] = a ? f / a : null;
  }
  return { ids, colours, banned, urlRefs, overflow, sides: [...sides], visible };
}

(async () => {
  const sets = [
    ["views", fs.readdirSync(path.join(mascot, "naomi", "views")).filter((f) => f.endsWith(".svg")).sort()],
    ["moods", fs.readdirSync(path.join(mascot, "naomi", "moods")).filter((f) => f.endsWith(".svg")).sort()],
  ];
  const browser = await chromium.launch({ channel: "chrome" });
  const page = await browser.newPage();
  await page.setContent("<!doctype html><title>naomi</title>");
  const lines = [];
  const say = (s = "") => (console.log(s), lines.push(s));
  const failures = [];
  const turmericWhere = {};
  const bodyColours = {};

  say(`Naomi — kiểm ${new Date().toISOString().slice(0, 10)} (check/naomi.cjs)`);
  say(`Ngưỡng: đuôi lộ ≥ ${VISIBLE.tail * 100} %, đốm đầu/đuôi lộ ≥ ${VISIBLE["head-spots"] * 100} %, đốm thân ≥ ${VISIBLE_IN_VIEWS["body-spots"] * 100} % (ba góc), màu thân cách Duo ≥ ΔE ${MIN_DUO_DE}`);
  say("");
  say(`${"tệp".padEnd(39)} ${"màu".padStart(4)} ${"lớp".padStart(4)} ${"tràn".padStart(5)}   ${"đuôi".padStart(5)} ${"đốm đầu".padStart(8)} ${"đốm đuôi".padStart(9)} ${"đốm thân".padStart(9)}`);
  for (const [set, files] of sets) {
    for (const f of files) {
      const text = fs.readFileSync(path.join(mascot, "naomi", set, f), "utf8");
      const groups = [...Object.keys(VISIBLE), ...Object.keys(VISIBLE_IN_VIEWS)];
      const r = await page.evaluate(analyse, { svgText: text, groups }).catch((e) => ({ error: String(e) }));
      const bad = [];
      if (r.error) bad.push(r.error);
      else {
        const notTokens = [...new Set(r.colours.map((c) => c.value).filter((v) => !tokenOf[v]))];
        if (notTokens.length) bad.push(`không phải token: ${notTokens.join(", ")}`);
        if (r.banned.length) bad.push(`thẻ cấm: ${r.banned.join(", ")}`);
        if (r.urlRefs) bad.push("có url(#…)");
        const missing = REQUIRED.filter((id) => !r.ids.includes(id));
        if (missing.length) bad.push(`thiếu lớp: ${missing.join(", ")}`);
        const dup = r.ids.filter((id, i) => r.ids.indexOf(id) !== i);
        if (dup.length) bad.push(`id trùng: ${[...new Set(dup)].join(", ")}`);
        for (const c of r.colours) {
          const name = tokenOf[c.value];
          const held = c.chain.some((id) => id.endsWith("-held"));
          const layer = c.chain.find((id) => BODY.includes(id) || ["eyes", "eyelids", "props", "props-head", "fx", "fx-back", "scene", "shadow"].includes(id)) || c.chain[0];
          if (name && name.startsWith("turmeric-")) {
            const where = held ? `${layer} (đồ cầm)` : layer;
            (turmericWhere[name] ||= new Set()).add(where);
            if (BODY.includes(layer) && !held) bad.push(`${name} trên ${c.chain.join(" ‹ ")}`);
          }
          if (BODY.includes(layer) && !held && name) bodyColours[name] = c.value;
        }
        if (r.overflow) bad.push(`tràn khung ${r.overflow} px (${r.sides.join(", ")})`);
        const limits = set === "views" ? { ...VISIBLE, ...VISIBLE_IN_VIEWS } : VISIBLE;
        for (const [id, min] of Object.entries(limits)) {
          const v = r.visible[id];
          if (v === null || v === undefined) bad.push(`không có ${id}`);
          else if (v < min) bad.push(`${id} chỉ lộ ${(v * 100).toFixed(0)} %`);
        }
      }
      const pct = (id) => (r.visible && typeof r.visible[id] === "number" ? `${(r.visible[id] * 100).toFixed(0)} %` : "—");
      say(
        `${(bad.length ? "FAIL " : "ok   ") + `${set}/${f}`.padEnd(34)} ${String(r.colours ? new Set(r.colours.map((c) => c.value)).size : "?").padStart(4)} ${String(r.ids ? r.ids.length : "?").padStart(4)} ${String(r.overflow ?? "?").padStart(5)}   ${pct("tail").padStart(5)} ${pct("head-spots").padStart(8)} ${pct("tail-spots").padStart(9)} ${pct("body-spots").padStart(9)}`
      );
      for (const b of bad) say(`       ${b}`);
      if (bad.length) failures.push(f);
    }
  }
  await browser.close();

  say("");
  say("Màu nghệ dùng ở đâu (luật: không tô miệng, tay, chân, đuôi, thân, đầu):");
  for (const [name, where] of Object.entries(turmericWhere).sort()) say(`  ${name.padEnd(14)} ${[...where].sort().join(", ")}`);
  say("");
  say(`Màu trên thân Naomi và màu Duo gần nhất (ΔE OKLab, phải ≥ ${MIN_DUO_DE}):`);
  for (const [name, hex] of Object.entries(bodyColours).sort()) {
    const n = nearestDuo(hex);
    const ok = n.de >= MIN_DUO_DE;
    if (!ok) failures.push(`duo:${name}`);
    say(`  ${ok ? "ok  " : "FAIL"} ${name.padEnd(12)} ${hex}  gần ${n.name.padEnd(16)} ΔE ${n.de.toFixed(3)}`);
  }
  say("");
  say(failures.length ? `${failures.length} lỗi.` : "Không lỗi.");
  if (process.argv[2]) fs.writeFileSync(process.argv[2], lines.join("\n") + "\n");
  process.exit(failures.length ? 1 : 0);
})();
