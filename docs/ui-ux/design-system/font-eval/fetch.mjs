// Fetch Google Fonts CSS (as Chrome sees it) for each candidate and download the
// latin + vietnamese woff2 subsets into ./dl/<slug>/. Writes ./dl/faces.json:
// [{ family, slug, subset, weight, file, bytes, unicodeRange }].
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36";

const CANDIDATES = [
  ["Geist", "wght@400..700"],
  ["Be Vietnam Pro", "wght@400;500;600;700"],
  ["Lexend", "wght@400..700"],
  ["Plus Jakarta Sans", "wght@400..700"],
  ["Nunito", "wght@400..700"],
  ["Manrope", "wght@400..700"],
  ["Bricolage Grotesque", "opsz,wght@12..96,400..700"],
];
const KEEP = new Set(["latin", "vietnamese"]);

const faces = [];
for (const [family, axes] of CANDIDATES) {
  const slug = family.toLowerCase().replace(/\s+/g, "-");
  const url = `https://fonts.googleapis.com/css2?family=${family.replace(/ /g, "+")}:${axes}&display=swap`;
  const css = await (await fetch(url, { headers: { "User-Agent": UA } })).text();
  const dir = path.join(here, "dl", slug);
  await mkdir(dir, { recursive: true });
  const re = /\/\*\s*([a-z-]+)\s*\*\/\s*@font-face\s*\{([^}]*)\}/g;
  let m;
  while ((m = re.exec(css))) {
    const [, subset, body] = m;
    if (!KEEP.has(subset)) continue;
    const src = /url\((https:\/\/fonts\.gstatic\.com\/[^)]+\.woff2)\)/.exec(body)?.[1];
    const weight = /font-weight:\s*([^;]+);/.exec(body)?.[1].trim();
    const unicodeRange = /unicode-range:\s*([^;]+);/.exec(body)?.[1].trim();
    if (!src) continue;
    const buf = Buffer.from(await (await fetch(src)).arrayBuffer());
    if (buf.subarray(0, 4).toString("latin1") !== "wOF2") throw new Error(`not woff2: ${src}`);
    const file = `${slug}-${subset}-${weight.replace(/\s+/g, "_")}.woff2`;
    await writeFile(path.join(dir, file), buf);
    faces.push({ family, slug, subset, weight, file: `${slug}/${file}`, bytes: buf.length, unicodeRange });
  }
  console.log(family, faces.filter((f) => f.family === family).map((f) => `${f.subset}@${f.weight}:${f.bytes}`).join(" "));
}
await writeFile(path.join(here, "dl", "faces.json"), JSON.stringify(faces, null, 2));
