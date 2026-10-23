"""Find the objects in the media bucket that nothing points at, and remove them
-- slowly.

Objects are orphaned in ordinary ways. Deleting a lesson removes its
`video_assets` row but not the files. `--purge` scripts and E2E clean-ups
remove certificates and leave the PDFs. A signed upload URL that was used but
never confirmed (an avatar picked and abandoned, a banner never saved) leaves
a picture no row names. And every "delete the old one" in the services is best
effort (`storage.delete_quietly`), so a bucket that refused once leaves a file
behind for good.

What counts as claimed, family by family -- the five prefixes this platform
writes, and nothing else in the bucket is ever looked at:

  videos/<asset id>/...         a `video_assets` row with that id
  avatars/<user id>/<file>      exactly the picture some `users.avatar_url` names
  banners/<file>                exactly the picture some `banners.image_url` names
  certificates/<code>.pdf       a `certificates` row with that code
  lesson-images/<course>/<file> exactly the picture some article's Markdown names

Then the rules that keep a mistake here from being permanent -- the bucket
has no versioning configured, and the nightly backup is of the database, not
of the files:

* **Young objects are left alone.** Under `YOUNG` old, an unclaimed object is
  most likely an upload whose confirmation has not arrived yet.
* **Mark first, delete much later.** An orphan is written to `orphan_objects`
  the first night it is seen and deleted only once that mark is `QUARANTINE`
  old and the object is still unclaimed. The quarantine is as long as database
  backups are kept, so a restored backup always finds the files it names; a
  claim that comes back clears the mark.
* **A night that looks wrong stops.** If most of one family would be newly
  marked, the database being read is far more likely to be the wrong one (or
  a lookup broken) than the files to have been abandoned all at once: nothing
  is written, and the log says why. `force` is for an operator who has read
  the report and knows the purge was real.
* **Exact keys, read back.** Deletion names every key and reads which ones
  the bucket refused; a refused key keeps its mark for the next night.
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Banner, Certificate, Lesson, OrphanObject, User, VideoAsset
from app.services.storage import (
    BANNER_PREFIX,
    LESSON_IMAGE_PREFIX,
    ObjectStorage,
    StoredObject,
)

logger = logging.getLogger(__name__)

VIDEOS = "videos/"
AVATARS = "avatars/"
BANNERS = f"{BANNER_PREFIX}/"
CERTIFICATES = "certificates/"
LESSON_IMAGES = f"{LESSON_IMAGE_PREFIX}/"
#: With the slash: `videos` alone would also list `videosX/...`.
MANAGED_PREFIXES = (VIDEOS, AVATARS, BANNERS, CERTIFICATES, LESSON_IMAGES)

#: A lesson-image key anywhere in an article's Markdown, whatever host its URL
#: names -- for the same reason as `_key_in_url`. It stops at whatever cannot
#: be in a key this platform mints (`)`, a space, a quote), so a title after
#: the URL is not read as part of it.
_LESSON_IMAGE_IN_TEXT = re.compile(re.escape(LESSON_IMAGES) + r"[A-Za-z0-9._/-]+")

#: Longer than any signed upload URL lives (`upload_url_ttl_seconds`, an hour)
#: with room for a browser that took its time.
YOUNG = timedelta(days=1)
#: As long as database backups are kept (`BACKUP_KEEP`, 14 nightly dumps).
QUARANTINE = timedelta(days=14)
#: A family is suspicious when more than this share of it would be newly
#: marked in one night...
VALVE_FRACTION = 0.5
#: ...and at least this many objects: three abandoned avatars out of four is
#: an ordinary week, not a broken lookup.
VALVE_MINIMUM = 20


def _key_in_url(url: str | None, prefix: str) -> str | None:
    """The bucket key a stored public URL names, whatever host served it.

    Read from the path rather than by stripping today's public base URL: the
    rows keep absolute URLs, and the day the bucket moves to another domain
    every old URL would otherwise stop being recognised as ours -- and its
    picture would look abandoned. Matching too much is the safe direction
    here: it can only keep an object, never delete one.
    """
    if url is None:
        return None
    at = url.find(f"/{prefix}")
    return url[at + 1 :] if at >= 0 else None


@dataclass(frozen=True)
class Ownership:
    """Every object the database currently names, family by family."""

    video_assets: frozenset[str]
    avatar_keys: frozenset[str]
    banner_keys: frozenset[str]
    certificate_codes: frozenset[str]
    lesson_image_keys: frozenset[str] = frozenset()

    def claims(self, key: str) -> bool:
        if key.startswith(VIDEOS):
            return key[len(VIDEOS) :].split("/", 1)[0] in self.video_assets
        if key.startswith(AVATARS):
            return key in self.avatar_keys
        if key.startswith(BANNERS):
            return key in self.banner_keys
        if key.startswith(CERTIFICATES):
            name = key[len(CERTIFICATES) :]
            return name.endswith(".pdf") and name.removesuffix(".pdf") in self.certificate_codes
        if key.startswith(LESSON_IMAGES):
            return key in self.lesson_image_keys
        raise ValueError(f"not a key this sweeper manages: {key}")


async def load_ownership(session: AsyncSession) -> Ownership:
    assets = await session.scalars(select(VideoAsset.id))
    avatars = await session.scalars(select(User.avatar_url).where(User.avatar_url.is_not(None)))
    banners = await session.scalars(select(Banner.image_url))
    codes = await session.scalars(select(Certificate.code))
    # Every article that mentions the folder at all, published or not: a draft
    # is an instructor's work in progress, and its pictures are as claimed as
    # those of a live course.
    articles = await session.scalars(
        select(Lesson.article_content).where(Lesson.article_content.contains(LESSON_IMAGES))
    )
    return Ownership(
        video_assets=frozenset(str(asset) for asset in assets),
        avatar_keys=frozenset(
            key for url in avatars if (key := _key_in_url(url, AVATARS)) is not None
        ),
        banner_keys=frozenset(
            key for url in banners if (key := _key_in_url(url, BANNERS)) is not None
        ),
        certificate_codes=frozenset(codes),
        lesson_image_keys=frozenset(
            key for text in articles for key in _LESSON_IMAGE_IN_TEXT.findall(text or "")
        ),
    )


@dataclass
class SweepReport:
    """What one night found and did. `applied` is False on a dry run and on a
    night the valve stopped; the lists then say what would have happened."""

    scanned: int = 0
    claimed: int = 0
    young: int = 0
    #: Unclaimed and marked tonight for the first time.
    marked: list[StoredObject] = field(default_factory=list)
    #: Unclaimed, marked earlier, quarantine not over.
    waiting: int = 0
    #: Unclaimed past the quarantine, and gone.
    deleted: list[StoredObject] = field(default_factory=list)
    #: Past the quarantine, but the bucket would not delete them.
    refused: list[str] = field(default_factory=list)
    #: Marks dropped: the object was claimed again, or is no longer there.
    cleared: int = 0
    applied: bool = False
    halted: str | None = None

    def lines(self) -> list[str]:
        mb = 1024 * 1024
        freed = sum(obj.size for obj in self.deleted) / mb
        marked = sum(obj.size for obj in self.marked) / mb
        out = [
            f"scanned {self.scanned}: claimed {self.claimed}, young {self.young}",
            f"marked {len(self.marked)} ({marked:.1f} MB), waiting {self.waiting}, "
            f"cleared {self.cleared}",
            f"deleted {len(self.deleted)} ({freed:.1f} MB), refused {len(self.refused)}",
        ]
        if self.halted:
            out.append(f"HALTED: {self.halted}")
        elif not self.applied:
            out.append("dry run: nothing was written or deleted")
        return out


def _family(key: str) -> str:
    return next(prefix for prefix in MANAGED_PREFIXES if key.startswith(prefix))


def _suspicious(marked: Iterable[StoredObject], totals: Counter[str]) -> str | None:
    """A family most of which would be marked tonight, or None."""
    new = Counter(_family(obj.key) for obj in marked)
    for family, count in sorted(new.items()):
        if count >= VALVE_MINIMUM and count > VALVE_FRACTION * totals[family]:
            return (
                f"{count} of {totals[family]} objects under {family} would be marked at once; "
                "check which database this is, then run scripts.sweep_orphans --apply --force"
            )
    return None


async def sweep(
    session: AsyncSession,
    storage: ObjectStorage,
    *,
    apply: bool,
    now: datetime | None = None,
    quarantine: timedelta = QUARANTINE,
    force: bool = False,
) -> SweepReport:
    """One night: list, compare, mark, and delete what has waited long enough."""
    now = now or datetime.now(UTC)
    ownership = await load_ownership(session)
    report = SweepReport()

    totals: Counter[str] = Counter()
    unclaimed: dict[str, StoredObject] = {}
    for prefix in MANAGED_PREFIXES:
        for obj in storage.list_objects(prefix):
            report.scanned += 1
            totals[prefix] += 1
            if ownership.claims(obj.key):
                report.claimed += 1
            elif now - obj.last_modified < YOUNG:
                report.young += 1
            else:
                unclaimed[obj.key] = obj

    marks = {mark.key: mark for mark in await session.scalars(select(OrphanObject))}
    due: list[StoredObject] = []
    for key, obj in unclaimed.items():
        mark = marks.get(key)
        if mark is None:
            report.marked.append(obj)
        elif mark.created_at <= now - quarantine:
            due.append(obj)
        else:
            report.waiting += 1
    stale = [key for key in marks if key not in unclaimed]
    report.cleared = len(stale)

    if not force and (reason := _suspicious(report.marked, totals)) is not None:
        report.halted = reason
        report.deleted = due
        logger.error("orphan sweep halted: %s", reason)
        return report

    if not apply:
        report.deleted = due
        return report

    # Marks first, in their own commit: a bucket that fails below must not
    # cost tonight's bookkeeping.
    if stale:
        await session.execute(delete(OrphanObject).where(OrphanObject.key.in_(stale)))
    session.add_all(OrphanObject(key=obj.key, size_bytes=obj.size) for obj in report.marked)
    await session.commit()

    if due:
        refused = set(storage.delete_keys([obj.key for obj in due]))
        report.refused = sorted(refused)
        report.deleted = [obj for obj in due if obj.key not in refused]
        if report.refused:
            logger.warning("orphan sweep: the bucket refused %d deletions", len(report.refused))
        # The object goes first, then its mark: a mark outliving its object
        # is cleared tomorrow, an object outliving its mark is waited for
        # again from the start.
        if report.deleted:
            await session.execute(
                delete(OrphanObject).where(
                    OrphanObject.key.in_([obj.key for obj in report.deleted])
                )
            )
            await session.commit()

    report.applied = True
    return report
