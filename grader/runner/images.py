"""The sandbox images, named and built in one place.

The tests, CI and the grading worker all have to mean the same thing when they
say "the Python sandbox". A tag repeated in three files is a tag that will
eventually differ in one of them, and the failure would be a submission graded
against an image nobody meant to ship -- so the name lives here and everything
else imports it.

Building from Python rather than a shell script keeps one command working on
the Windows dev machine and on the Linux CI runner alike.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

IMAGES_DIR = Path(__file__).resolve().parents[1] / "images"

PYTHON_IMAGE = "devpath-sandbox-python:v1"

# tag -> build context. One entry per language: v1 supports Python only, and
# this map is what makes adding Java later a new line rather than a new design.
IMAGES: dict[str, Path] = {PYTHON_IMAGE: IMAGES_DIR / "python"}


def build(tag: str) -> None:
    subprocess.run(["docker", "build", "--tag", tag, str(IMAGES[tag])], check=True)


def build_all() -> None:
    for tag in IMAGES:
        build(tag)


if __name__ == "__main__":
    build_all()
