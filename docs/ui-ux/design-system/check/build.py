"""Emulate the Design System page: compile tokens.css from tokens.json and wrap
each preview with tokens.css + bundle.css, so the previews can be screenshotted
locally. Output: one HTML per preview in ./out.

    python docs/ui-ux/design-system/check/build.py
    NODE_PATH=frontend/node_modules node docs/ui-ux/design-system/check/shoot.cjs
    NODE_PATH=frontend/node_modules node docs/ui-ux/design-system/check/motion.cjs
"""
import json, re, sys
from pathlib import Path

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "project"
OUT = Path(__file__).parent / "out"
OUT.mkdir(exist_ok=True)
t = json.loads((ROOT / "tokens.json").read_text(encoding="utf-8"))

def val(v):
    m = re.fullmatch(r"\{(.+)\}", v)
    return f"var(--{m.group(1)})" if m else v

lines = [":root, [data-theme=\"light\"] {"]
for tok in t["color"]["tokens"]:
    v = tok["value"] if isinstance(tok["value"], str) else tok["value"]["light"]
    lines.append(f"  --{tok['name']}: {val(v)};")
for tok in t.get("shadow", {}).get("tokens", []):
    lines.append(f"  --{tok['name']}: {tok['value']};")
lines.append("}")
lines.append(":root {")
for fam in ("spacing", "radius", "duration", "easing"):
    for tok in t[fam]["tokens"]:
        lines.append(f"  --{tok['name']}: {tok['value']};")
for k, v in t["type"]["families"].items():
    lines.append(f"  --font-{k}: {v};")
lines.append("}")
for g in t["type"]["groups"]:
    for s in g["styles"]:
        fam = s.get("family", g["family"])
        decl = [f"font-family: var(--font-{fam})", f"font-size: {s['fontSize']}", f"line-height: {s['lineHeight']}", f"font-weight: {s['fontWeight']}"]
        if "letterSpacing" in s:
            decl.append(f"letter-spacing: {s['letterSpacing']}")
        if s["name"] == "eyebrow":
            pass
        lines.append(f".{s['name']} {{ {'; '.join(decl)}; }}")
tokens_css = "\n".join(lines)
bundle = (ROOT / "components" / "bundle.css").read_text(encoding="utf-8")
imp, rest = bundle.split("\n", 1)

for prev in sorted((ROOT / "components").glob("*/preview.html")):
    html = prev.read_text(encoding="utf-8")
    first = html.split("\n", 1)[0]
    h = re.search(r"height=(\d+)", first)
    height = int(h.group(1)) if h else 120
    inject = f"<style>{imp}\n{tokens_css}\n{rest}</style>"
    html = html.replace("<head>", "<head>" + inject, 1).replace("<html", "<html data-theme=\"light\"", 1)
    (OUT / f"{prev.parent.name}.html").write_text(html, encoding="utf-8")
    print(prev.parent.name, height)
