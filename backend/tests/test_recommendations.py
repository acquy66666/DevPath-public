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
from app.services.content_based import rebuild_embeddings
from app.services.hybrid import (
    FUSION_DEPTH,
    SOURCE_COLLABORATIVE,
    SOURCE_CONTENT,
    SOURCE_POPULAR,
)
from app.services.recommendations import (
    CachedList,
    CachedRecommendation,
    dumps,
    for_user,
    loads,
    popular_courses,
    rebuild,
)
from tests.api.fakes import MemoryRecommendationCache
from tests.test_content_based import FakeEmbedder, axis

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
        self,
        title: str,
        *,
        status: str = "published",
        deleted: bool = False,
        students: int = 0,
        category: Category | None = None,
    ) -> Course:
        # `students` runs into the thousands in the popularity tests on
        # purpose: the dev database holds seeded courses whose highest count is
        # 12, and a fallback query reads the whole catalogue.
        course = Course(
            instructor_id=self.instructor.id,
            category_id=(category or self.category).id,
            title=title,
            slug=f"{title.lower()}-{uuid.uuid4().hex[:8]}",
            price=Decimal("0"),
            status=status,
            students_count=students,
            published_at=datetime.now(UTC) if status == "published" else None,
            deleted_at=datetime.now(UTC) if deleted else None,
        )
        self.session.add(course)
        await self.session.flush()
        return course

    async def other_category(self, name: str) -> Category:
        category = Category(name=name, slug=f"{name.lower()}-{uuid.uuid4().hex[:8]}")
        self.session.add(category)
        await self.session.flush()
        return category

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


def from_the_model(served) -> list:
    """Just the rows the batch chose.

    Every block is topped up with popular courses now, so a test about what
    the model decided has to say so -- otherwise it is also asserting on the
    dev database's seeded catalogue, which is not its business.
    """
    return [
        item.course.id for item in served.items if item.sources != (SOURCE_POPULAR,)
    ]


def cached(*items: tuple[uuid.UUID, float, uuid.UUID], minutes_ago: int = 30) -> CachedList:
    return CachedList(
        generated_at=datetime.now(UTC) - timedelta(minutes=minutes_ago),
        items=[
            CachedRecommendation(
                course_id=course,
                score=score,
                because=because,
                sources=(SOURCE_COLLABORATIVE,),
            )
            for course, score, because in items
        ],
    )


async def test_nothing_cached_still_fills_the_block_with_popular_courses(
    db_session: AsyncSession, world: World
):
    """A brand-new reader: no history, so neither half of the model has
    anything. The block shows popular courses rather than nothing, and says so
    -- `computed` stays False because nothing was computed *for them*."""
    reader = await world.student("nguoi-moi")
    await world.course("Ai cũng học", students=9000)

    served = await for_user(
        db_session, user_id=reader.id, limit=8, cache=MemoryRecommendationCache()
    )

    assert served.generated_at is None
    assert served.computed is False
    assert served.items != []
    assert all(item.sources == (SOURCE_POPULAR,) for item in served.items)
    assert served.items[0].course.title == "Ai cũng học"


async def test_a_cached_empty_list_says_the_model_did_run(
    db_session: AsyncSession, world: World
):
    """The model ran and had nothing. That is still a different answer from
    "nobody has looked", and `computed` is what carries the difference -- the
    block itself is filled either way."""
    reader = await world.student("hoc-vien")
    cache = MemoryRecommendationCache()
    cache.write(reader.id, cached())

    served = await for_user(db_session, user_id=reader.id, limit=8, cache=cache)

    assert served.computed is True
    assert all(item.sources == (SOURCE_POPULAR,) for item in served.items)


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

    chosen = [item for item in served.items if item.sources != (SOURCE_POPULAR,)]
    assert [item.course.id for item in chosen] == [first.id, second.id, third.id]
    assert [item.score for item in chosen] == [3.0, 2.0, 1.0]
    assert all(item.because is not None and item.because.id == history.id for item in chosen)


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

    assert from_the_model(served) == [still_new.id]


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

    assert from_the_model(served) == [live.id]


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

    assert from_the_model(served) == [live.id]
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


# --- The fallback: popularity ------------------------------------------------


async def test_popular_courses_come_back_most_students_first(
    db_session: AsyncSession, world: World
):
    quiet = await world.course("Ít người", students=5000)
    busy = await world.course("Đông người", students=9000)

    found = await popular_courses(db_session, limit=2, exclude=set())

    assert [course.id for course, _, _ in found] == [busy.id, quiet.id]


async def test_the_readers_own_categories_come_first(
    db_session: AsyncSession, world: World
):
    """"Phổ biến theo danh mục": somebody who has only taken Python courses is
    better served by the third-most-popular Python course than by the most
    popular one on the platform."""
    elsewhere = await world.course("Đông nhất, khác lĩnh vực", students=9000)
    mine = await world.course(
        "Ít hơn, đúng lĩnh vực",
        students=6000,
        category=await world.other_category("Python"),
    )

    found = await popular_courses(
        db_session, limit=2, exclude=set(), category_ids=[mine.category_id]
    )

    assert [course.id for course, _, _ in found] == [mine.id, elsewhere.id]


async def test_courses_the_reader_already_has_are_never_offered(
    db_session: AsyncSession, world: World
):
    owned = await world.course("Đã học", students=9000)
    other = await world.course("Chưa học", students=8000)

    found = await popular_courses(db_session, limit=5, exclude={owned.id})

    assert owned.id not in [course.id for course, _, _ in found]
    assert other.id in [course.id for course, _, _ in found]


async def test_a_draft_or_a_withdrawn_course_is_never_popular(
    db_session: AsyncSession, world: World
):
    draft = await world.course("Nháp", students=9000, status="draft")
    removed = await world.course("Đã gỡ", students=9000, deleted=True)

    found = await popular_courses(db_session, limit=5, exclude=set())

    ids = [course.id for course, _, _ in found]
    assert draft.id not in ids
    assert removed.id not in ids


async def test_popularity_carries_the_instructor_and_category_for_the_card(
    db_session: AsyncSession, world: World
):
    course = await world.course("Đông người", students=9000)

    (row, instructor, category), *_ = await popular_courses(
        db_session, limit=1, exclude=set()
    )

    assert row.id == course.id
    assert instructor.id == world.instructor.id
    assert category.id == world.category.id


# --- The fallback: topping up a short block ---------------------------------


async def test_a_short_block_is_topped_up_with_popular_courses(
    db_session: AsyncSession, world: World
):
    reader = await world.student("hoc-vien")
    history = await world.course("History")
    modelled = await world.course("Model chon")
    await world.takes(reader, history)
    # As many popular courses as there are gaps to fill. The block must be
    # fillable from this test's own rows: on the dev database the seeded
    # catalogue quietly supplied the missing ones, on CI's empty one it did
    # not, and the block came back two long.
    popular = [
        await world.course(f"Đông người {n}", students=9000 - n) for n in range(3)
    ]

    cache = MemoryRecommendationCache()
    cache.write(reader.id, cached((modelled.id, 3.0, history.id)))

    served = await for_user(db_session, user_id=reader.id, limit=4, cache=cache)

    assert served.items[0].course.id == modelled.id
    assert served.items[0].sources == (SOURCE_COLLABORATIVE,)
    assert [item.course.id for item in served.items[1:]] == [c.id for c in popular]
    assert all(item.sources == (SOURCE_POPULAR,) for item in served.items[1:])


async def test_a_full_block_is_left_alone(db_session: AsyncSession, world: World):
    """The fallback fills gaps; it does not dilute a block the model filled."""
    reader = await world.student("hoc-vien")
    history = await world.course("History")
    chosen = [await world.course(f"C{n}") for n in range(2)]
    await world.takes(reader, history)
    await world.course("Đông người", students=9000)

    cache = MemoryRecommendationCache()
    cache.write(
        reader.id,
        cached(*[(course.id, 3.0 - n, history.id) for n, course in enumerate(chosen)]),
    )

    served = await for_user(db_session, user_id=reader.id, limit=2, cache=cache)

    assert [item.course.id for item in served.items] == [c.id for c in chosen]
    assert all(item.sources == (SOURCE_COLLABORATIVE,) for item in served.items)


async def test_the_top_up_never_repeats_what_the_model_already_chose(
    db_session: AsyncSession, world: World
):
    reader = await world.student("hoc-vien")
    history = await world.course("History")
    modelled = await world.course("Model chon, cung dong nguoi", students=9000)
    await world.takes(reader, history)

    cache = MemoryRecommendationCache()
    cache.write(reader.id, cached((modelled.id, 3.0, history.id)))

    served = await for_user(db_session, user_id=reader.id, limit=5, cache=cache)

    assert [item.course.id for item in served.items].count(modelled.id) == 1


async def test_the_top_up_never_offers_a_course_the_reader_has(
    db_session: AsyncSession, world: World
):
    reader = await world.student("hoc-vien")
    history = await world.course("Da hoc va rat dong", students=9000)
    await world.takes(reader, history)

    served = await for_user(
        db_session, user_id=reader.id, limit=5, cache=MemoryRecommendationCache()
    )

    assert history.id not in [item.course.id for item in served.items]


async def test_the_top_up_prefers_the_categories_the_reader_has_shown_interest_in(
    db_session: AsyncSession, world: World
):
    python = await world.other_category("Python")
    reader = await world.student("hoc-vien")
    history = await world.course("Da hoc", category=python)
    await world.takes(reader, history)
    await world.course("Dong nhat nhung khac linh vuc", students=9000)
    mine = await world.course("Dung linh vuc", students=6000, category=python)

    served = await for_user(
        db_session, user_id=reader.id, limit=5, cache=MemoryRecommendationCache()
    )

    assert served.items[0].course.id == mine.id


# --- The batch, blending both halves ----------------------------------------


async def test_the_batch_blends_both_halves(db_session: AsyncSession, world: World):
    """Two readers whose enrolments overlap give the collaborative half
    something to say; the vectors give the content half something to say; the
    entry written carries items attributed to each."""
    reader = await world.student("hoc-vien")
    friend = await world.student("ban-hoc")
    shared = await world.course("Cung hoc")
    theirs = await world.course("Ban hoc them")
    lookalike = await world.course("Giong khoa da hoc")

    await world.takes(reader, shared)
    await world.takes(friend, shared)
    await world.takes(friend, theirs)

    await rebuild_embeddings(
        db_session,
        embedder=FakeEmbedder(
            {"Cung hoc": axis(0), "Giong khoa da hoc": axis(0), "Ban hoc them": axis(7)}
        ),
        course_ids=[shared.id, theirs.id, lookalike.id],
    )

    writer = RecordingWriter()
    await rebuild(db_session, writer, embedding_model="fake-embed-1")

    mine = {item.course_id: item for item in writer.written[reader.id].items}
    assert SOURCE_COLLABORATIVE in mine[theirs.id].sources
    assert SOURCE_CONTENT in mine[lookalike.id].sources


async def test_a_just_published_course_the_content_half_puts_first_makes_the_top(
    db_session: AsyncSession, world: World
):
    """The cold-start path the hybrid exists for, measured in
    `docs/report/assets/phase-4/recommender-eval.md`.

    The reader has H. Six classmates each took H and one more course, so the
    collaborative half offers six courses. A course published today has no
    takers, and its vector is H's own: the content half ranks it first. Every
    course is somewhat alike (45° here; ≥ 0,747 in the real catalogue), so the
    content half lists the six as well.

    Fed whole, every one of the six is in *both* lists and outscores a course
    in one -- the new course comes last. Cut to `FUSION_DEPTH`, a course the
    content half puts first can only be beaten by courses in both top lists,
    of which there are at most `FUSION_DEPTH - 1`.
    """
    reader = await world.student("hoc-vien")
    history = await world.course("H")
    await world.takes(reader, history)
    classmates_took = []
    for n in range(FUSION_DEPTH + 1):
        classmate = await world.student(f"ban-{n}")
        course = await world.course(f"C{n}")
        await world.takes(classmate, history)
        await world.takes(classmate, course)
        classmates_took.append(course)
    published_today = await world.course("Moi xuat ban")

    await rebuild_embeddings(
        db_session,
        embedder=FakeEmbedder(
            {
                "Moi xuat ban": axis(0),
                "H": axis(0),
                **{f"C{n}": axis(0, n + 1) for n in range(FUSION_DEPTH + 1)},
            }
        ),
        course_ids=[history.id, published_today.id, *(c.id for c in classmates_took)],
    )

    writer = RecordingWriter()
    await rebuild(db_session, writer, embedding_model="fake-embed-1")

    ranked = [item.course_id for item in writer.written[reader.id].items]
    assert published_today.id in ranked[:FUSION_DEPTH]


async def test_a_course_both_halves_chose_says_so(
    db_session: AsyncSession, world: World
):
    reader = await world.student("hoc-vien")
    friend = await world.student("ban-hoc")
    shared = await world.course("Cung hoc")
    agreed = await world.course("Ca hai nua deu chon")

    await world.takes(reader, shared)
    await world.takes(friend, shared)
    await world.takes(friend, agreed)

    await rebuild_embeddings(
        db_session,
        embedder=FakeEmbedder({"Cung hoc": axis(0), "Ca hai nua deu chon": axis(0)}),
        course_ids=[shared.id, agreed.id],
    )

    writer = RecordingWriter()
    await rebuild(db_session, writer, embedding_model="fake-embed-1")

    mine = {item.course_id: item for item in writer.written[reader.id].items}
    assert mine[agreed.id].sources == (SOURCE_COLLABORATIVE, SOURCE_CONTENT)


async def test_a_cached_item_remembers_which_halves_chose_it() -> None:
    """The round trip through Redis has to keep `sources`, or every item comes
    back looking like it came from nowhere."""
    original = CachedList(
        generated_at=datetime(2026, 9, 20, 3, 0, tzinfo=UTC),
        items=[
            CachedRecommendation(
                course_id=uuid.uuid4(),
                score=0.03,
                because=uuid.uuid4(),
                sources=(SOURCE_COLLABORATIVE, SOURCE_CONTENT),
            )
        ],
    )

    restored = loads(dumps(original))

    assert restored == original
    assert restored.items[0].sources == (SOURCE_COLLABORATIVE, SOURCE_CONTENT)
