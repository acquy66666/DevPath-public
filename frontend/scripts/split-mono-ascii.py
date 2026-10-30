"""Split Geist Mono's latin subset into ASCII and the rest.

    pip install fonttools brotli   # once, anywhere (not a frontend dependency)
    python frontend/scripts/split-mono-ascii.py

Reads public/fonts/geist-mono-latin.woff2 (Google's file, kept as the source)
and writes geist-mono-ascii.woff2 (U+0020-007E) and geist-mono-latin-rest.woff2
(everything else the latin file draws). app/fonts.css declares both with those
unicode-ranges, and the pages that show code in their first screen preload
only the ASCII one: the home page's example submission and the course covers
use nothing else, and it is 14 KB against 23 (Phase 7 performance,
docs/report/assets/phase-7/performance.md). Both keep the weight axis and every
OpenType feature, so the text draws exactly as before.

Run again whenever geist-mono-latin.woff2 is replaced.
"""

from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

FONTS = Path(__file__).resolve().parent.parent / "public" / "fonts"
SOURCE = FONTS / "geist-mono-latin.woff2"
ASCII = set(range(0x20, 0x7F))


def write(codepoints: set[int], name: str) -> None:
    font = TTFont(SOURCE)
    options = subset.Options()
    options.flavor = "woff2"
    options.layout_features = ["*"]
    options.name_IDs = ["*"]
    options.name_languages = ["*"]
    options.notdef_outline = True
    options.glyph_names = False
    subsetter = subset.Subsetter(options)
    subsetter.populate(unicodes=codepoints)
    subsetter.subset(font)
    font.flavor = "woff2"
    font.save(FONTS / name)
    print(f"{name}: {len(codepoints)} code points, {(FONTS / name).stat().st_size} bytes")


def main() -> None:
    drawn = set(TTFont(SOURCE).getBestCmap())
    write(drawn & ASCII, "geist-mono-ascii.woff2")
    write(drawn - ASCII, "geist-mono-latin-rest.woff2")


if __name__ == "__main__":
    main()
