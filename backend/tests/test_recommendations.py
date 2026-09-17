"""The cache between the nightly batch and the page.

Three things are worth testing here and none of them is the model, which has
its own file:

* what goes into Redis comes back out the same -- ids as ids, not strings;
* the batch writes an entry for **every** user it considered, including those
  it has nothing for, because a stale entry from yesterday is worse than an
  empty one from today;
* the cache is re-checked on the way out. A day is long enough for a course to
  be unpublished, withdrawn, or enrolled in by the person being told about it,
  and the batch cannot know about any of that.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models import Category, Course, Enrollment, User
from app.services.recommendations import (
    CachedList,
    CachedRecommendation,
    dumps,
    for_user,
    loads,
    rebuild,
)
from tests.api.fakes import MemoryRecommendationCache

PASSWORD = "mật-khẩu-đủ-dài"


class RecordingWriter:
    """The batch's Redis handle, as a dictionary."""

    def __init__(self) -> None:
        self.written: dict[uuid.UUID, CachedList] = {}

    def write(self, user_id: uuid.UUID, cached: CachedList) -> None:
        self.written[user_id] = cached


# --- What is stored --------------------------------------------------------


def test_a_cached_list_survives_the_round_trip():
    """Ids must come back as UUIDs. A string id would compare unequal to every
    row it is looked up against, and the block would silently render empty."""
    original = CachedList(
        generated_at=datetime(2026, 9, 18, 3, 0, tzinfo=UTC),
        items=[
            CachedRecommendation(course_id=uuid.uuid4(), score=1.5, because=uuid.uuid4()),
            CachedRecommendation(course_id=uuid.uuid4(), score=0.25, because=uuid.uuid4()),
        ],
    )

    restored = loads(dumps(original))

    assert restored == original
    assert all(isinstance(item.course_id, uuid.UUID) for item in restored.items)


def test_an_empty_list_is_a_value_not_a_missing_key():
    """"We looked and found nothing" has to be storable, or it cannot be told
    apart from "nobody has looked yet"."""
    empty = CachedList(generated_at=datetime.now(UTC), items=[])
    assert loads(dumps(empty)).items == []


# --- The database-backed half ---------------------------------------------


class World:
    def __init__(self, session: AsyncSession, category: Category, instructor: User):
        self.session = session
        self.category = category
        self.instructor = instructor

    async def course(
        self, title: str, *, status: str = "published", deleted: bool = False
    ) -> Course:
        course = Course(
            instructor_id=self.instructor.id,
            category_id=self.category.id,
            title=title,
            slug=f"{title.lower()}-{uuid.uuid4().hex[:8]}",
            price=Decimal("0"),
            status=status,
            published_at=datetime.now(UTC) if status == "published" else None,
            deleted_at=datetime.now(UTC) if deleted else None,
        )
        self.session.add(course)
        await self.session.flush()
        return course

    async def student(self, name: str) -> User:
        user = User(
            email=f"{name}-{uuid.uuid4().hex[:8]}@example.com",
            full_name=name,
            password_hash=hash_password(PASSWORD),
            role="student",
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def takes(self, user: User, course: Course, *, completed: bool = False) -> None:
        self.session.add(
            Enrollment(
                user_id=user.id,
                course_id=course.id,
                completed_at=datetime.now(UTC) if completed else None,
            )
        )
        await self.session.flush()


@pytest.fixture
async def world(db_session: AsyncSession) -> World:
    instructor = User(
        email=f"gv-{uuid.uuid4().hex[:8]}@example.com",
        full_name="Giảng viên",
        password_hash=hash_password(PASSWORD),
        role="instructor",
    )
    category = Category(name="Lập trình", slug=f"lap-trinh-{uuid.uuid4().hex[:8]}")
    db_session.add_all([instructor, category])
    await db_session.flush()
    return World(db_session, category, instructor)


def cached(*items: tuple[uuid.UUID, float, uuid.UUID], minutes_ago: int = 30) -> CachedList:
    return CachedList(
        generated_at=datetime.now(UTC) - timedelta(minutes=minutes_ago),
        items=[
            CachedRecommendation(course_id=course, score=score, because=because)
            for course, score, because in items
        ],
    )


async def test_nothing_cached_is_reported_as_nothing_computed(
    db_session: AsyncSession, world: World
):
    reader = await world.student("nguoi-moi")

    served = await for_user(
        db_session, user_id=reader.id, limit=8, cache=MemoryRecommendationCache()
    )

    assert served.items == []
    assert served.generated_at is None
    assert served.computed is False


async def test_a_cached_empty_list_says_the_model_did_run(
    db_session: AsyncSession, world: World
):
    reader = await world.student("hoc-vien")
    cache = MemoryRecommendationCache()
    cache.write(reader.id, cached())

    served = await for_user(db_session, user_id=reader.id, limit=8, cache=cache)

    assert served.items == []
    assert served.computed is True


async def test_the_cached_order_is_the_order_served(db_session: AsyncSession, world: World):
    """The scores came from the model; re-sorting here on anything else would
    quietly disagree with it."""
    reader = await world.student("hoc-vien")
    history = await world.course("History")
    first, second, third = [await world.course(f"C{n}") for n in (1, 2, 3)]
    await world.takes(reader, history)

    cache = MemoryRecommendationCache()
    cache.write(
        reader.id,
        cached(
            (first.id, 3.0, history.id),
            (second.id, 2.0, history.id),
            (third.id, 1.0, history.id),
        ),
    )

    served = await for_user(db_session, user_id=reader.id, limit=8, cache=cache)

    assert [item.course.id for item in served.items] == [first.id, second.id, third.id]
    assert [item.score for item in served.items] == [3.0, 2.0, 1.0]
    assert all(item.because is not None and item.because.id == history.id for item in served.items)


async def test_a_course_enrolled_in_since_the_batch_is_dropped(
    db_session: AsyncSession, world: World
):
    """The most likely staleness of all: the batch ran at three in the morning
    and the student signed up for one of its suggestions at breakfast."""
    reader = await world.student("hoc-vien")
    history = await world.course("History")
    signed_up, still_new = await world.course("SignedUp"), await world.course("StillNew")
    await world.takes(reader, history)
    await world.takes(reader, signed_up)

    cache = MemoryRecommendationCache()
    cache.write(
        reader.id, cached((signed_up.id, 3.0, history.id), (still_new.id, 1.0, history.id))
    )

    served = await for_user(db_session, user_id=reader.id, limit=8, cache=cache)

    assert [item.course.id for item in served.items] == [still_new.id]


async def test_a_course_pulled_from_the_catalogue_is_dropped(
    db_session: AsyncSession, world: World
):
    reader = await world.student("hoc-vien")
    history = await world.course("History")
    unpublished = await world.course("Unpublished", status="draft")
    withdrawn = await world.course("Withdrawn", deleted=True)
    live = await world.course("Live")
    await world.takes(reader, history)

    cache = MemoryRecommendationCache()
    cache.write(
        reader.id,
        cached(
            (unpublished.id, 5.0, history.id),
            (withdrawn.id, 4.0, history.id),
            (live.id, 1.0, history.id),
        ),
    )

    served = await for_user(db_session, user_id=reader.id, limit=8, cache=cache)

    assert [item.course.id for item in served.items] == [live.id]


async def test_a_withdrawn_reason_leaves_the_recommendation_standing(
    db_session: AsyncSession, world: World
):
    """The course that earned this has been removed. The suggestion is still
    the model's, so it stays -- only the sentence explaining it goes."""
    reader = await world.student("hoc-vien")
    gone = await world.course("Gone", deleted=True)
    live = await world.course("Live")
    await world.takes(reader, gone)

    cache = MemoryRecommendationCache()
    cache.write(reader.id, cached((live.id, 1.0, gone.id)))

    served = await for_user(db_session, user_id=reader.id, limit=8, cache=cache)

    assert [item.course.id for item in served.items] == [live.id]
    # Named, because the reader took it -- describing their own history is not
    # advertising a withdrawn course. The API decides whether to link it.
    assert served.items[0].because is not None


async def test_limit_is_applied_after_the_checks(db_session: AsyncSession, world: World):
    """Asked for two, and the top of the cached list is already gone.

    Cutting to the limit first and filtering afterwards would return one -- the
    reason the cache holds more than any page shows.
    """
    reader = await world.student("hoc-vien")
    history = await world.course("History")
    taken = await world.course("Taken")
    a, b = await world.course("A"), await world.course("B")
    await world.takes(reader, history)
    await world.takes(reader, taken)

    cache = MemoryRecommendationCache()
    cache.write(
        reader.id,
        cached((taken.id, 9.0, history.id), (a.id, 2.0, history.id), (b.id, 1.0, history.id)),
    )

    served = await for_user(db_session, user_id=reader.id, limit=2, cache=cache)

    assert [item.course.id for item in served.items] == [a.id, b.id]


# --- The batch --------------------------------------------------------------


async def test_the_batch_writes_an_entry_for_every_user_it_considered(
    db_session: AsyncSession, world: World
):
    """Including the ones it has nothing for.

    `lonely` took a course nobody else took, so the model cannot suggest
    anything. Leaving them without an entry would be indistinguishable from
    never having run; an empty list dated today says what actually happened.
    """
    shared_a, shared_b, lonely_course = [
        await world.course(t) for t in ("SharedA", "SharedB", "Lonely")
    ]
    veteran = await world.student("veteran")
    await world.takes(veteran, shared_a, completed=True)
    await world.takes(veteran, shared_b, completed=True)

    newcomer = await world.student("newcomer")
    await world.takes(newcomer, shared_a, completed=True)

    lonely = await world.student("lonely")
    await world.takes(lonely, lonely_course)

    writer = RecordingWriter()
    await rebuild(db_session, writer)

    assert {newcomer.id, veteran.id, lonely.id} <= set(writer.written)
    assert [item.course_id for item in writer.written[newcomer.id].items] == [shared_b.id]
    assert writer.written[newcomer.id].items[0].because == shared_a.id
    assert writer.written[lonely.id].items == []


async def test_every_entry_from_one_run_carries_the_same_timestamp(
    db_session: AsyncSession, world: World
):
    """One run, one `generated_at`: the page shows how old the batch is, not
    how long each user's slice of it took."""
    a, b = await world.course("A"), await world.course("B")
    for name in ("one", "two"):
        student = await world.student(name)
        await world.takes(student, a)
        await world.takes(student, b)

    writer = RecordingWriter()
    await rebuild(db_session, writer)

    stamps = {entry.generated_at for entry in writer.written.values()}
    assert len(stamps) == 1


async def test_the_batch_caps_each_list(db_session: AsyncSession, world: World):
    catalogue = [await world.course(f"C{n}") for n in range(6)]
    veteran = await world.student("veteran")
    for course in catalogue:
        await world.takes(veteran, course, completed=True)
    newcomer = await world.student("newcomer")
    await world.takes(newcomer, catalogue[0], completed=True)

    writer = RecordingWriter()
    await rebuild(db_session, writer, top_n=2)

    assert len(writer.written[newcomer.id].items) == 2
