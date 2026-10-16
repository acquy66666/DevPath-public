"""Homepage banners: what the homepage shows, and the admin arranging them.

**What is live** is decided at read time, never stored: switched on, and now
inside `[starts_at, ends_at)` with an empty bound meaning "no bound". A banner
set to come down on Sunday comes down on Sunday without anybody or any job
touching the row. The homepage shows at most `MAX_LIVE` of them, in order.

**Pictures go straight from the browser to the bucket**, exactly like avatars:
the API signs a PUT for a fresh key under `banners/`, the browser uploads,
then sends the key back with the banner. The key is believed only if it sits
directly under that prefix -- otherwise a banner could be hung on any object
in the bucket. A picture that is replaced or whose banner is deleted is
removed after the commit, best effort (`delete_quietly`).
"""

import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import DomainError
from app.models import Banner
from app.services.storage import BANNER_PREFIX, ObjectStorage, banner_key, delete_quietly

#: How many banners the homepage rotates through. More is a carousel nobody
#: waits to see the end of.
MAX_LIVE = 5

BannerStatus = Literal["live", "scheduled", "ended", "off"]


class BannerNotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "BANNER_NOT_FOUND"


class BannerImageKeyError(DomainError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "BANNER_IMAGE_KEY_INVALID"


class BannerPeriodError(DomainError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "INVALID_BANNER_PERIOD"


class InvalidBannerOrderError(DomainError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "INVALID_ORDER"


def status_of(banner: Banner, now: datetime) -> BannerStatus:
    if not banner.is_active:
        return "off"
    if banner.ends_at is not None and banner.ends_at <= now:
        return "ended"
    if banner.starts_at is not None and banner.starts_at > now:
        return "scheduled"
    return "live"


# --- Reading ---------------------------------------------------------------


async def list_live(session: AsyncSession, *, now: datetime | None = None) -> list[Banner]:
    """What the homepage shows right now, in order."""
    now = now or datetime.now(UTC)
    return list(
        await session.scalars(
            select(Banner)
            .where(
                Banner.is_active,
                or_(Banner.starts_at.is_(None), Banner.starts_at <= now),
                or_(Banner.ends_at.is_(None), Banner.ends_at > now),
            )
            .order_by(Banner.position, Banner.created_at)
            .limit(MAX_LIVE)
        )
    )


async def list_all(session: AsyncSession) -> list[Banner]:
    """Every banner, in the homepage's order. A handful of rows: unpaginated."""
    return list(await session.scalars(select(Banner).order_by(Banner.position, Banner.created_at)))


# --- The picture -----------------------------------------------------------


def upload_ticket(
    storage: ObjectStorage, *, filename: str, content_type: str, size_bytes: int
) -> tuple[str, str, int]:
    """(signed PUT URL, key, seconds it lives) for one new picture."""
    ttl = get_settings().upload_url_ttl_seconds
    key = banner_key(filename)
    url = storage.presigned_put_url(key, content_type, ttl, size_bytes=size_bytes)
    return url, key, ttl


def _check_key(key: str) -> None:
    prefix = f"{BANNER_PREFIX}/"
    if not key.startswith(prefix) or "/" in key[len(prefix) :] or len(key) == len(prefix):
        raise BannerImageKeyError("Ảnh banner phải được tải lên qua trang quản trị")


def _own_key(banner: Banner, storage: ObjectStorage) -> str | None:
    """The bucket key of the banner's picture, when it is one of ours."""
    base = storage.public_url("")
    if not banner.image_url.startswith(base):
        return None
    key = banner.image_url[len(base) :]
    return key if key.startswith(f"{BANNER_PREFIX}/") else None


# --- Writing ---------------------------------------------------------------


def _check_period(starts_at: datetime | None, ends_at: datetime | None) -> None:
    if starts_at is not None and ends_at is not None and ends_at <= starts_at:
        raise BannerPeriodError("Thời điểm gỡ phải sau thời điểm bắt đầu hiện")


async def _get(session: AsyncSession, banner_id: uuid.UUID) -> Banner:
    banner = await session.get(Banner, banner_id)
    if banner is None:
        raise BannerNotFoundError("Không tìm thấy banner")
    return banner


async def create(
    session: AsyncSession,
    storage: ObjectStorage,
    *,
    title: str,
    image_key: str,
    link_url: str | None,
    is_active: bool,
    starts_at: datetime | None,
    ends_at: datetime | None,
) -> Banner:
    """A new banner goes last."""
    _check_key(image_key)
    _check_period(starts_at, ends_at)
    last = await session.scalar(select(func.max(Banner.position)))
    banner = Banner(
        title=title,
        image_url=storage.public_url(image_key),
        link_url=link_url,
        is_active=is_active,
        starts_at=starts_at,
        ends_at=ends_at,
        position=0 if last is None else last + 1,
    )
    session.add(banner)
    await session.commit()
    await session.refresh(banner)
    return banner


async def update(
    session: AsyncSession, storage: ObjectStorage, banner_id: uuid.UUID, changes: dict
) -> Banner:
    """Apply what was sent. A new `image_key` replaces the picture."""
    banner = await _get(session, banner_id)
    stale_key: str | None = None

    if "image_key" in changes and changes["image_key"] is not None:
        _check_key(changes["image_key"])
        stale_key = _own_key(banner, storage)
        banner.image_url = storage.public_url(changes["image_key"])
    for field in ("title", "link_url", "is_active", "starts_at", "ends_at"):
        if field in changes and not (field in ("title", "is_active") and changes[field] is None):
            setattr(banner, field, changes[field])
    _check_period(banner.starts_at, banner.ends_at)

    await session.commit()
    await session.refresh(banner)
    new_key = _own_key(banner, storage)
    if stale_key is not None and stale_key != new_key:
        delete_quietly(storage, stale_key)
    return banner


async def reorder(session: AsyncSession, ordered_ids: list[uuid.UUID]) -> list[Banner]:
    """The whole order at once, every banner exactly once."""
    banners = await list_all(session)
    by_id = {banner.id: banner for banner in banners}
    if len(ordered_ids) != len(set(ordered_ids)) or set(ordered_ids) != set(by_id):
        raise InvalidBannerOrderError("Danh sách sắp xếp phải có đủ và chỉ một lần mỗi banner")
    for position, banner_id in enumerate(ordered_ids):
        by_id[banner_id].position = position
    await session.commit()
    return await list_all(session)


async def delete(session: AsyncSession, storage: ObjectStorage, banner_id: uuid.UUID) -> None:
    banner = await _get(session, banner_id)
    key = _own_key(banner, storage)
    await session.delete(banner)
    await session.commit()
    if key is not None:
        delete_quietly(storage, key)
