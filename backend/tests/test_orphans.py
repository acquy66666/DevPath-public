"""The orphan sweeper: what it claims, what it marks, and what it deletes.

Deleting is the one thing the bucket cannot undo, so most of these are about
what the sweeper must NOT delete: a claimed object, a young one, one whose
quarantine is not over, one claimed again in the meantime, anything outside
the prefixes it manages -- and everything at all on a night when the
database looks wrong.
"""

import random
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    CERTIFICATE_CODE_ALPHABET,
    CERTIFICATE_CODE_LENGTH,
    Banner,
    Category,
    Certificate,
    Course,
    Enrollment,
    OrphanObject,
    User,
    VideoAsset,
)
from app.services import orphans
from app.services.storage import StoredObject
from tests.api.fakes import FakeStorage
from tests.api.test_video_upload import make_lesson, make_user

NOW = datetime.now(UTC)
OLD = timedelta(days=30)


class BucketStorage(FakeStorage):
    """A fake bucket with a listing: keys, sizes and ages."""

    def __init__(self) -> None:
        super().__init__()
        self.listing: dict[str, StoredObject] = {}
        self.deleted_keys: list[str] = []
        #: Keys the bucket will not delete.
        self.refuse: set[str] = set()

    def put(self, key: str, *, age: timedelta = OLD, size: int = 100) -> str:
        self.listing[key] = StoredObject(key=key, size=size, last_modified=NOW - age)
        return key

    def list_objects(self, prefix: str):
        return iter([obj for key, obj in sorted(self.listing.items()) if key.startswith(prefix)])

    def delete_keys(self, keys):
        refused = [key for key in keys if key in self.refuse]
        for key in keys:
            if key not in self.refuse:
                self.deleted_keys.append(key)
                self.listing.pop(key, None)
        return refused


@pytest.fixture
async def storage(db_session: AsyncSession) -> BucketStorage:
    """A fake bucket, and no marks but the ones the test makes.

    The tests run inside a transaction on whatever database is configured --
    on a developer machine, the dev database, where a real sweep may have
    left marks. Clearing them here is rolled back with everything else.
    """
    await db_session.execute(delete(OrphanObject))
    return BucketStorage()


def _hex() -> str:
    return uuid.uuid4().hex


def _code() -> str:
    return "".join(random.choices(CERTIFICATE_CODE_ALPHABET, k=CERTIFICATE_CODE_LENGTH))


async def _video(session: AsyncSession) -> uuid.UUID:
    asset_id = uuid.uuid4()
    session.add(
        VideoAsset(id=asset_id, storage_key=f"videos/{asset_id}/original.mp4", status="ready")
    )
    await session.flush()
    return asset_id


async def _user(session: AsyncSession, avatar_url: str | None = None) -> User:
    user = User(
        email=f"u-{_hex()[:8]}@example.com",
        full_name="Người dùng",
        password_hash="x",
        role="student",
        avatar_url=avatar_url,
    )
    session.add(user)
    await session.flush()
    return user


async def _certificate(session: AsyncSession) -> str:
    teacher = await _user(session)
    student = await _user(session)
    category = Category(name=f"Danh mục {_hex()[:6]}", slug=f"dm-{_hex()[:8]}")
    session.add(category)
    await session.flush()
    course = Course(
        instructor_id=teacher.id,
        category_id=category.id,
        title="Khóa học",
        slug=f"khoa-{_hex()[:8]}",
        price=Decimal("0"),
        status="published",
        published_at=NOW,
    )
    session.add(course)
    await session.flush()
    enrollment = Enrollment(user_id=student.id, course_id=course.id)
    session.add(enrollment)
    await session.flush()
    code = _code()
    session.add(
        Certificate(
            enrollment_id=enrollment.id,
            code=code,
            recipient_name="Học viên",
            course_title="Khóa học",
            instructor_name="Giảng viên",
            issued_at=NOW,
            pdf_key=f"certificates/{code}.pdf",
        )
    )
    await session.flush()
    return code


async def _marks(session: AsyncSession) -> dict[str, OrphanObject]:
    return {mark.key: mark for mark in await session.scalars(select(OrphanObject))}


# --- Who claims what --------------------------------------------------------


def test_a_key_is_claimed_by_the_row_that_names_it() -> None:
    asset = str(uuid.uuid4())
    ownership = orphans.Ownership(
        video_assets=frozenset({asset}),
        avatar_keys=frozenset({"avatars/u1/a.png"}),
        banner_keys=frozenset({"banners/b.png"}),
        certificate_codes=frozenset({"ABCDEFGHJKLMNPQR"}),
    )

    # A video is claimed as a whole: original, HLS segments and transcript.
    assert ownership.claims(f"videos/{asset}/original.mp4")
    assert ownership.claims(f"videos/{asset}/hls/segment_007.ts")
    assert not ownership.claims(f"videos/{uuid.uuid4()}/original.mp4")
    # An avatar or banner only as the exact picture in use.
    assert ownership.claims("avatars/u1/a.png")
    assert not ownership.claims("avatars/u1/old.png")
    assert ownership.claims("banners/b.png")
    assert not ownership.claims("banners/gone.png")
    # A certificate PDF by the code in its name.
    assert ownership.claims("certificates/ABCDEFGHJKLMNPQR.pdf")
    assert not ownership.claims("certificates/ABCDEFGHJKLMNPQS.pdf")
    assert not ownership.claims("certificates/ABCDEFGHJKLMNPQR.txt")


def test_a_lesson_picture_is_claimed_only_as_the_exact_file_an_article_names() -> None:
    course = uuid.uuid4()
    ownership = orphans.Ownership(
        video_assets=frozenset(),
        avatar_keys=frozenset(),
        banner_keys=frozenset(),
        certificate_codes=frozenset(),
        lesson_image_keys=frozenset({f"lesson-images/{course}/a.png"}),
    )

    assert ownership.claims(f"lesson-images/{course}/a.png")
    # Pasted, then deleted from the text before saving.
    assert not ownership.claims(f"lesson-images/{course}/b.png")


async def test_ownership_is_read_from_every_table_that_names_an_object(
    db_session: AsyncSession, storage: BucketStorage
) -> None:
    asset = await _video(db_session)
    owner = await _user(db_session)
    avatar = f"avatars/{owner.id}/{_hex()}.png"
    owner.avatar_url = storage.public_url(avatar)
    # Written while the bucket was served from another address: still ours.
    moved = await _user(db_session)
    moved_avatar = f"avatars/{moved.id}/{_hex()}.webp"
    moved.avatar_url = f"https://old-cdn.example/{moved_avatar}"
    # A Google profile picture names nothing in our bucket.
    await _user(db_session, avatar_url="https://lh3.googleusercontent.com/a/xyz=s96-c")
    banner = f"banners/{_hex()}.png"
    db_session.add(Banner(title="Banner", image_url=storage.public_url(banner)))
    code = await _certificate(db_session)
    await db_session.flush()

    ownership = await orphans.load_ownership(db_session)

    assert str(asset) in ownership.video_assets
    assert {avatar, moved_avatar} <= ownership.avatar_keys
    assert banner in ownership.banner_keys
    assert code in ownership.certificate_codes


async def test_a_lesson_picture_is_claimed_by_any_article_that_names_it(
    db_session: AsyncSession, storage: BucketStorage
) -> None:
    owner = await make_user(db_session, "instructor")
    lesson = await make_lesson(db_session, owner, lesson_type="article")
    course = uuid.uuid4()
    first = f"lesson-images/{course}/{_hex()}.png"
    titled = f"lesson-images/{course}/{_hex()}.gif"
    moved = f"lesson-images/{course}/{_hex()}.webp"
    lesson.article_content = (
        f"Mở terminal:\n\n![Cửa sổ terminal]({storage.public_url(first)})\n\n"
        f'Rồi bấm chạy: ![Nút chạy]({storage.public_url(titled)} "Nút Run")\n\n'
        # Written while the bucket was served from another address: still ours.
        f"![Cũ](https://old-cdn.example/devpath-media/{moved})"
    )
    await db_session.flush()

    ownership = await orphans.load_ownership(db_session)

    assert {first, titled, moved} <= ownership.lesson_image_keys
    assert ownership.claims(titled)


async def test_a_lesson_picture_nothing_names_is_marked_like_any_orphan(
    db_session: AsyncSession, storage: BucketStorage
) -> None:
    owner = await make_user(db_session, "instructor")
    lesson = await make_lesson(db_session, owner, lesson_type="article")
    kept = f"lesson-images/{uuid.uuid4()}/{_hex()}.png"
    lesson.article_content = f"![Ảnh]({storage.public_url(kept)})"
    await db_session.flush()
    storage.put(kept)
    dropped = storage.put(f"lesson-images/{uuid.uuid4()}/{_hex()}.png")

    report = await orphans.sweep(db_session, storage, apply=True, now=NOW)

    assert [obj.key for obj in report.marked] == [dropped]
    assert report.deleted == []


# --- Marking, quarantine, deleting ------------------------------------------


async def test_the_first_night_marks_and_deletes_nothing(
    db_session: AsyncSession, storage: BucketStorage
) -> None:
    asset = await _video(db_session)
    claimed = storage.put(f"videos/{asset}/hls/index.m3u8")
    orphan = storage.put(f"videos/{uuid.uuid4()}/original.mp4", size=5_000)
    # Uploaded an hour ago and not confirmed yet: an upload in flight.
    young = storage.put(f"avatars/{uuid.uuid4()}/{_hex()}.png", age=timedelta(hours=1))

    report = await orphans.sweep(db_session, storage, apply=True, now=NOW)

    assert [obj.key for obj in report.marked] == [orphan]
    assert report.deleted == []
    assert storage.deleted_keys == []
    assert set(await _marks(db_session)) == {orphan}
    assert claimed in storage.listing and young in storage.listing
    assert (report.claimed, report.young) == (1, 1)


async def test_an_orphan_goes_only_once_its_quarantine_is_over(
    db_session: AsyncSession, storage: BucketStorage
) -> None:
    orphan = storage.put(f"certificates/{_code()}.pdf")
    await orphans.sweep(db_session, storage, apply=True, now=NOW)

    early = await orphans.sweep(
        db_session, storage, apply=True, now=NOW + orphans.QUARANTINE - timedelta(days=1)
    )
    assert early.deleted == [] and early.waiting == 1
    assert orphan in storage.listing

    due = await orphans.sweep(
        db_session, storage, apply=True, now=NOW + orphans.QUARANTINE + timedelta(days=1)
    )
    assert [obj.key for obj in due.deleted] == [orphan]
    assert storage.deleted_keys == [orphan]
    assert await _marks(db_session) == {}


async def test_an_object_claimed_again_is_forgiven(
    db_session: AsyncSession, storage: BucketStorage
) -> None:
    """A restored backup brings back the row; its file must still be there."""
    asset_id = uuid.uuid4()
    key = storage.put(f"videos/{asset_id}/original.mp4")
    await orphans.sweep(db_session, storage, apply=True, now=NOW)
    assert key in await _marks(db_session)

    db_session.add(VideoAsset(id=asset_id, storage_key=key, status="ready"))
    await db_session.flush()
    report = await orphans.sweep(
        db_session, storage, apply=True, now=NOW + orphans.QUARANTINE + timedelta(days=1)
    )

    assert report.deleted == []
    assert report.cleared == 1
    assert key in storage.listing
    assert await _marks(db_session) == {}


async def test_a_mark_for_an_object_that_is_gone_is_dropped(
    db_session: AsyncSession, storage: BucketStorage
) -> None:
    key = storage.put(f"banners/{_hex()}.png")
    await orphans.sweep(db_session, storage, apply=True, now=NOW)
    del storage.listing[key]

    report = await orphans.sweep(db_session, storage, apply=True, now=NOW)

    assert report.cleared == 1
    assert await _marks(db_session) == {}


async def test_a_dry_run_writes_nothing(
    db_session: AsyncSession, storage: BucketStorage
) -> None:
    orphan = storage.put(f"videos/{uuid.uuid4()}/original.mp4")

    report = await orphans.sweep(db_session, storage, apply=False, now=NOW)

    assert [obj.key for obj in report.marked] == [orphan]
    assert report.applied is False
    assert await _marks(db_session) == {}
    assert storage.deleted_keys == []


async def test_a_key_the_bucket_refuses_stays_marked(
    db_session: AsyncSession, storage: BucketStorage
) -> None:
    key = storage.put(f"certificates/{_code()}.pdf")
    storage.refuse.add(key)
    await orphans.sweep(db_session, storage, apply=True, now=NOW)

    report = await orphans.sweep(
        db_session, storage, apply=True, now=NOW + orphans.QUARANTINE + timedelta(days=1)
    )

    assert report.refused == [key]
    assert report.deleted == []
    assert key in await _marks(db_session)


async def test_most_of_a_family_unclaimed_stops_the_night(
    db_session: AsyncSession, storage: BucketStorage
) -> None:
    """What a sweep reading the wrong database looks like: everything is an
    orphan. It stops before writing anything, family by family -- avatars
    alone looking unclaimed is what a broken avatar lookup would do, and
    videos being fine says nothing about that."""
    for _ in range(3):
        storage.put(f"videos/{await _video(db_session)}/original.mp4")
    for _ in range(orphans.VALVE_MINIMUM):
        storage.put(f"avatars/{uuid.uuid4()}/{_hex()}.png")

    halted = await orphans.sweep(db_session, storage, apply=True, now=NOW)

    assert halted.halted is not None and "avatars" in halted.halted
    assert halted.applied is False
    assert await _marks(db_session) == {}

    forced = await orphans.sweep(db_session, storage, apply=True, now=NOW, force=True)
    assert forced.halted is None
    assert len(await _marks(db_session)) == orphans.VALVE_MINIMUM


async def test_nothing_outside_the_managed_prefixes_is_touched(
    db_session: AsyncSession, storage: BucketStorage
) -> None:
    foreign = storage.put("exports/2026-10-01.csv")
    lookalike = storage.put("videosX/not-a-video.mp4")

    report = await orphans.sweep(
        db_session, storage, apply=True, now=NOW + orphans.QUARANTINE * 3
    )

    assert report.scanned == 0
    assert {foreign, lookalike} <= set(storage.listing)
    assert await _marks(db_session) == {}


@pytest.mark.parametrize("family", orphans.MANAGED_PREFIXES)
def test_every_managed_prefix_ends_in_a_slash(family: str) -> None:
    """`videos` without the slash would also list `videosX/...`."""
    assert family.endswith("/")
