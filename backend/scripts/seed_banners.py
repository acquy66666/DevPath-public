"""Demo homepage banners, pictures included.

Three banners that point at things the other seeds made real: the
`CHAOMUNG50` code (`scripts.seed_coupons`), the Python courses, and the weekly
leaderboard (`scripts.seed_study`). The pictures are horizontal gradients the
script draws itself -- a PNG is a few lines of `zlib` -- so no image library
and no stock photo is needed; the title is drawn over the picture by the page.

Written **through the service** (`services/banners.create`), after uploading
each picture under `banners/` exactly where an admin's upload would land, so
the rows are ones the API itself would make. Idempotent by title; `--purge`
removes exactly these banners and their pictures.

    python -m scripts.seed_banners [--purge]
"""

import argparse
import asyncio
import struct
import zlib
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.models import Banner
from app.services import banners as banners_service
from app.services.storage import ObjectStorage, banner_key, build_storage

WIDTH, HEIGHT = 1680, 640

Colour = tuple[int, int, int]


@dataclass(frozen=True, slots=True)
class BannerPlan:
    title: str
    link_url: str
    left: Colour
    right: Colour


DEMO_BANNERS = [
    BannerPlan(
        title="Chào bạn mới: giảm 50% mọi khóa học với mã CHAOMUNG50",
        link_url="/khoa-hoc",
        left=(30, 64, 175),
        right=(124, 58, 237),
    ),
    BannerPlan(
        title="Học Python từ số không — bài tập được chấm tự động ngay khi nộp",
        link_url="/khoa-hoc?q=python",
        left=(4, 120, 87),
        right=(13, 148, 136),
    ),
    BannerPlan(
        title="Bảng xếp hạng tuần này: ai học chăm nhất?",
        link_url="/bang-xep-hang",
        left=(194, 65, 12),
        right=(219, 39, 119),
    ),
]


def gradient_png(left: Colour, right: Colour, width: int = WIDTH, height: int = HEIGHT) -> bytes:
    """A left-to-right gradient as a PNG, with nothing but the standard library."""
    row = bytearray()
    for x in range(width):
        t = x / (width - 1)
        row += bytes(round(a + (b - a) * t) for a, b in zip(left, right, strict=True))
    # Filter byte 0 (none) in front of every scanline; every scanline is the same.
    raw = (b"\x00" + bytes(row)) * height

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)  # 8-bit RGB
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


async def seed_banners(
    session: AsyncSession, storage: ObjectStorage, plans: list[BannerPlan] = DEMO_BANNERS
) -> int:
    """Create the banners that are missing. One already there is left alone."""
    titles = [plan.title for plan in plans]
    existing = set(await session.scalars(select(Banner.title).where(Banner.title.in_(titles))))
    written = 0
    for plan in plans:
        if plan.title in existing:
            continue
        key = banner_key("banner.png")
        storage.upload_bytes(gradient_png(plan.left, plan.right), key, "image/png")
        await banners_service.create(
            session,
            storage,
            title=plan.title,
            image_key=key,
            link_url=plan.link_url,
            is_active=True,
            starts_at=None,
            ends_at=None,
        )
        written += 1
    return written


async def purge(
    session: AsyncSession, storage: ObjectStorage, plans: list[BannerPlan] = DEMO_BANNERS
) -> int:
    """Remove exactly these banners, pictures included, through the service."""
    titles = [plan.title for plan in plans]
    ids = list(await session.scalars(select(Banner.id).where(Banner.title.in_(titles))))
    for banner_id in ids:
        await banners_service.delete(session, storage, banner_id)
    return len(ids)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--purge", action="store_true", help="Xóa đúng ba banner demo.")
    args = parser.parse_args()
    storage = build_storage()

    async with SessionLocal() as session:
        if args.purge:
            print(f"Đã xóa {await purge(session, storage)} banner.")
            return
        written = await seed_banners(session, storage)

    print(f"banner tạo mới: {written}")
    for plan in DEMO_BANNERS:
        print(f"  {plan.title}  ->  {plan.link_url}")
    print("\nXem ở trang chủ; sửa, tắt, sắp xếp ở /quan-tri/banner.")


if __name__ == "__main__":
    asyncio.run(main())
