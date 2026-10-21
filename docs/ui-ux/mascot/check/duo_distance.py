"""Distance between the colours DevPath reserves for its mascot and Duo's own.

Duo's values: design.duolingo.com/identity/color (read 21/10/2026).
DevPath values: docs/ui-ux/design-system/project/tokens.json.
"""
import math

def srgb_to_linear(c):
    c /= 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

def oklab(hexv):
    h = hexv.lstrip("#")
    r, g, b = (srgb_to_linear(int(h[i:i + 2], 16)) for i in (0, 2, 4))
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l, m, s = (math.copysign(abs(v) ** (1 / 3), v) for v in (l, m, s))
    L = 0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s
    A = 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s
    B = 0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s
    return L, A, B

def lch(hexv):
    L, A, B = oklab(hexv)
    return L, math.hypot(A, B), math.degrees(math.atan2(B, A)) % 360

def de(a, b):
    return math.dist(oklab(a), oklab(b))

DUO = {
    "Feather Green (than)": "#58CC02",
    "Mask Green (mang sang)": "#89E219",
    "Wing Overlay (canh)": "#43C000",
    "Beak Upper (mo tren)": "#FFC200",
    "Beak Lower/Feet (mo duoi, chan)": "#F49000",
}
OURS = {
    "jade-500 (than A, C)": "#039580",
    "jade-300 (mat pixel C, dom sang)": "#6fd3be",
    "jade-100 (bung A, than B)": "#ccf5ea",
    "jade-700 (dom A, mo B)": "#066254",
    "jade-900 (net, man hinh C)": "#05332b",
    "turmeric-300 (mong mat A, den C)": "#ffc84c",
    "red-500 (con bo cua A)": "#e24947",
}

print("OKLCH  L     C     h")
for name, v in {**DUO, **OURS}.items():
    L, C, h = lch(v)
    print(f"{name:36s} {v}  {L:.3f} {C:.3f} {h:6.1f}")

print("\nDelta E OK (x100): toi than Duo (Feather Green) va toi mau Duo gan nhat")
for name, v in OURS.items():
    nearest = min(DUO.items(), key=lambda kv: de(v, kv[1]))
    dh = abs(lch(v)[2] - lch(nearest[1])[2])
    dh = min(dh, 360 - dh)
    body = de(v, DUO["Feather Green (than)"]) * 100
    print(f"{name:34s} than={body:5.1f}  gan nhat: {nearest[0]:32s} dE={de(v, nearest[1]) * 100:5.1f}  dHue={dh:5.1f}")
