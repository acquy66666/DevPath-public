"""The content-based half of the recommender, checked on paper first.

Two things live here and they fail in different ways. `course_text` decides
*what* gets embedded -- get it wrong and every vector in the table is wrong in
the same direction, invisibly. `rebuild_embeddings` decides *when* a vector is
paid for again, and the failure there is a quota bill, not a wrong answer.

The vectors in these tests are axis vectors rather than anything a model would
produce: the cosine between two of them can be worked out in your head, so a
wrong ranking is wrong for a reason.
"""

import uuid
import zlib
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models import (
    EMBEDDING_DIMENSIONS,
    Category,
    Course,
    CourseEmbedding,
    Enrollment,
    User,
)
from app.services.content_based import (
    MAX_SOURCE_CHARS,
    CourseVector,
    course_text,
    load_vectors,
    rebuild_embeddings,
    recommend_from_history,
    similar_to,
)
from app.services.courses import CourseNotFoundError

PASSWORD = "mật-khẩu-đủ-dài"


def axis(*positions: int) -> list[float]:
    """A unit vector with ones on the given axes.

    Real embeddings are dense and unreadable; these are neither, which is the
    point -- the cosine between two of them can be worked out on paper.
    """
    vector = [0.0] * EMBEDDING_DIMENSIONS
    for position in positions:
        vector[position] = 1.0
    return vector


class FakeEmbedder:
    """An embedder that costs nothing and says what it was asked to embed.

    `vectors` maps a marker -- any substring of the text -- to the vector that
    text should get, so a test can place two courses next to each other and a
    third far away without inventing 768 numbers.
    """

    def __init__(
        self, vectors: dict[str, list[float]] | None = None, model: str = "fake-embed-1"
    ) -> None:
        self.vectors = vectors or {}
        self._model = model
        #: Every batch handed over, so a test can assert what was *not* paid for.
        self.calls: list[list[str]] = []

    @property
    def model(self) -> str:
        return self._model

    async def embed_similarity(self, texts) -> list[list[float]]:
        batch = list(texts)
        self.calls.append(batch)
        return [self._vector_for(text) for text in batch]

    @property
    def embedded(self) -> list[str]:
        return [text for call in self.calls for text in call]

    def _vector_for(self, text: str) -> list[float]:
        for marker, vector in self.vectors.items():
            if marker in text:
                return vector
        # Deterministic across runs -- `hash()` on a string is not -- and far
        # from every other default: one axis each.
        return axis(zlib.crc32(text.encode()) % EMBEDDING_DIMENSIONS)


def make_course(**kwargs) -> Course:
    """A course row in memory -- never added to a session."""
    fields = {
        "title": "Python cơ bản",
        "subtitle": "Học lập trình từ số 0",
        "description": "Khóa học dạy biến, vòng lặp và hàm.",
    }
    fields.update(kwargs)
    return Course(
        instructor_id=uuid.uuid4(),
        category_id=uuid.uuid4(),
        slug="python-co-ban",
        **fields,
    )


def test_course_text_carries_title_subtitle_category_and_description() -> None:
    text = course_text(make_course(), "Lập trình")

    assert "Python cơ bản" in text
    assert "Học lập trình từ số 0" in text
    assert "Lập trình" in text
    assert "Khóa học dạy biến, vòng lặp và hàm." in text


def test_course_text_leaves_no_gap_where_a_missing_field_was() -> None:
    """A course with no subtitle and no description still reads as a sentence.

    Blank lines where an optional field should have been are not cosmetic: the
    embedding is of the string, and a string that is half whitespace is a
    weaker signal than the same words without it.
    """
    text = course_text(make_course(subtitle=None, description=None), "Lập trình")

    assert "\n\n\n" not in text
    assert text == text.strip()
    assert "Python cơ bản" in text
    assert "Lập trình" in text


def test_course_text_cuts_a_long_description_at_a_word_boundary() -> None:
    """The model truncates silently past its input limit, so this does not."""
    word = "lập trình "
    course = make_course(description=word * 2000)

    text = course_text(course, "Lập trình")

    assert len(text) <= MAX_SOURCE_CHARS
    # Cut between words, not through one.
    assert not text.endswith("lậ")
    assert not text.endswith("trìn")
    # The heading survives the cut: it is the part that names the course.
    assert "Python cơ bản" in text


def test_course_text_stays_inside_the_limit_when_the_title_alone_is_enormous() -> None:
    """A pathological title cannot push the text past the model's limit."""
    course = make_course(title="a" * (MAX_SOURCE_CHARS * 2), description=None)

    assert len(course_text(course, "Lập trình")) <= MAX_SOURCE_CHARS


@pytest.mark.parametrize("blank", ["", "   ", "\n\n"])
def test_course_text_treats_a_blank_description_as_no_description(blank: str) -> None:
    text = course_text(make_course(description=blank), "Lập trình")

    assert text == course_text(make_course(description=None), "Lập trình")


# --- Filling the table ------------------------------------------------------


async def add_course(
    session: AsyncSession,
    *,
    title: str,
    description: str | None = "Mô tả khóa học.",
    status: str = "published",
    deleted: bool = False,
    category: Category | None = None,
) -> Course:
    """One course in the database, with the rows it cannot exist without."""
    if category is None:
        category = Category(name="Lập trình", slug=f"lt-{uuid.uuid4().hex[:8]}")
        session.add(category)
        await session.flush()

    instructor = User(
        email=f"gv-{uuid.uuid4().hex[:8]}@example.com",
        full_name="Giảng viên",
        password_hash=hash_password(PASSWORD),
        role="instructor",
    )
    session.add(instructor)
    await session.flush()

    course = Course(
        instructor_id=instructor.id,
        category_id=category.id,
        title=title,
        slug=f"{uuid.uuid4().hex[:12]}",
        description=description,
        status=status,
        published_at=datetime.now(tz=UTC) if status == "published" else None,
        deleted_at=datetime.now(tz=UTC) if deleted else None,
    )
    session.add(course)
    await session.flush()
    return course


async def stored(session: AsyncSession, course: Course) -> CourseEmbedding | None:
    return await session.scalar(
        select(CourseEmbedding).where(CourseEmbedding.course_id == course.id)
    )


async def test_rebuild_writes_one_vector_per_published_course(
    db_session: AsyncSession,
) -> None:
    """The whole-catalogue run, measured as a delta.

    The dev database already holds seeded courses and a rebuild reads every one
    of them, so the count that means anything is what a *second* run adds once
    the first has caught up -- which is also the shape the nightly job runs in.
    """
    embedder = FakeEmbedder()
    await rebuild_embeddings(db_session, embedder=embedder)

    python = await add_course(db_session, title="Python cơ bản")
    javascript = await add_course(db_session, title="JavaScript cơ bản")
    report = await rebuild_embeddings(db_session, embedder=embedder)

    assert report.embedded == 2
    for course in (python, javascript):
        row = await stored(db_session, course)
        assert row is not None
        assert row.embedding_model == "fake-embed-1"
        assert course.title in row.source_text
        assert len(row.embedding) == EMBEDDING_DIMENSIONS


async def test_rebuild_does_not_pay_twice_for_an_unchanged_course(
    db_session: AsyncSession,
) -> None:
    """The whole point of storing `source_text`: a second run costs nothing."""
    await add_course(db_session, title="Python cơ bản")
    embedder = FakeEmbedder()
    first = await rebuild_embeddings(db_session, embedder=embedder)
    assert first.embedded >= 1
    embedder.calls.clear()

    report = await rebuild_embeddings(db_session, embedder=embedder)

    assert report.embedded == 0
    # Every course the first run touched, and no new ones.
    assert report.unchanged == first.embedded + first.unchanged
    assert embedder.calls == []


async def test_rebuild_re_embeds_a_course_whose_words_changed(
    db_session: AsyncSession,
) -> None:
    course = await add_course(db_session, title="Python cơ bản")
    embedder = FakeEmbedder()
    await rebuild_embeddings(db_session, embedder=embedder)

    course.description = "Mô tả đã viết lại hoàn toàn."
    await db_session.flush()
    report = await rebuild_embeddings(db_session, embedder=embedder)

    assert report.embedded == 1
    row = await stored(db_session, course)
    assert "viết lại hoàn toàn" in row.source_text


async def test_rebuild_re_embeds_when_the_model_changes(
    db_session: AsyncSession,
) -> None:
    """Two models can share a width and still disagree about every sentence."""
    course = await add_course(db_session, title="Python cơ bản")
    mine = [course.id]
    await rebuild_embeddings(
        db_session, embedder=FakeEmbedder(model="old-model"), course_ids=mine
    )

    report = await rebuild_embeddings(
        db_session, embedder=FakeEmbedder(model="new-model"), course_ids=mine
    )

    assert report.embedded == 1
    row = await stored(db_session, course)
    assert row.embedding_model == "new-model"


async def test_rebuild_leaves_out_courses_nobody_can_be_shown(
    db_session: AsyncSession,
) -> None:
    """A draft and a withdrawn course are not candidates, so not embeddings."""
    published = await add_course(db_session, title="Python cơ bản")
    draft = await add_course(db_session, title="Bản nháp", status="draft")
    removed = await add_course(db_session, title="Đã gỡ", deleted=True)

    report = await rebuild_embeddings(
        db_session,
        embedder=FakeEmbedder(),
        course_ids=[published.id, draft.id, removed.id],
    )

    assert report.embedded == 1
    assert await stored(db_session, published) is not None
    assert await stored(db_session, draft) is None
    assert await stored(db_session, removed) is None


async def test_rebuild_can_be_pointed_at_one_course(db_session: AsyncSession) -> None:
    """What the publish hook uses: one course, not the whole catalogue."""
    wanted = await add_course(db_session, title="Python cơ bản")
    other = await add_course(db_session, title="JavaScript cơ bản")

    report = await rebuild_embeddings(
        db_session, embedder=FakeEmbedder(), course_ids=[wanted.id]
    )

    assert report.embedded == 1
    assert await stored(db_session, wanted) is not None
    assert await stored(db_session, other) is None


async def test_rebuild_embeds_the_category_name_with_the_course(
    db_session: AsyncSession,
) -> None:
    """The category is part of the text, which means it needs the join."""
    category = Category(name="Khoa học dữ liệu", slug=f"kh-{uuid.uuid4().hex[:8]}")
    db_session.add(category)
    await db_session.flush()
    course = await add_course(db_session, title="Pandas", category=category)

    await rebuild_embeddings(
        db_session, embedder=FakeEmbedder(), course_ids=[course.id]
    )

    row = await stored(db_session, course)
    assert "Khoa học dữ liệu" in row.source_text


# --- Reading it back --------------------------------------------------------


async def test_similar_ranks_by_cosine_and_leaves_out_the_course_itself(
    db_session: AsyncSession,
) -> None:
    """Axis vectors, so the ranking can be checked by hand.

    The target sits on axis 0. The near course sits on axes 0 and 1, which is
    45 degrees away -- cosine 1/sqrt(2). The far course shares no axis at all,
    which is cosine 0.
    """
    target = await add_course(db_session, title="Python cơ bản")
    near = await add_course(db_session, title="Python nâng cao")
    far = await add_course(db_session, title="Thiết kế đồ họa")
    await rebuild_embeddings(
        db_session,
        embedder=FakeEmbedder(
            {
                "Python cơ bản": axis(0),
                "Python nâng cao": axis(0, 1),
                "Thiết kế đồ họa": axis(5),
            }
        ),
        course_ids=[target.id, near.id, far.id],
    )

    found = await similar_to(db_session, course_id=target.id, limit=10)

    assert [item.course.id for item in found] == [near.id, far.id]
    assert found[0].score == pytest.approx(2**-0.5, abs=1e-6)
    assert found[1].score == pytest.approx(0.0, abs=1e-6)
    assert found[0].instructor.id == near.instructor_id
    assert found[0].category.id == near.category_id


async def test_similar_leaves_out_courses_nobody_may_be_shown(
    db_session: AsyncSession,
) -> None:
    """A course can be embedded and still not be a candidate: unpublishing
    deliberately keeps the vector, so this filter is the one doing the work."""
    target = await add_course(db_session, title="Python cơ bản")
    withdrawn = await add_course(db_session, title="Python nâng cao")
    await rebuild_embeddings(
        db_session,
        embedder=FakeEmbedder({"Python": axis(0)}),
        course_ids=[target.id, withdrawn.id],
    )

    withdrawn.status = "draft"
    await db_session.flush()

    assert await similar_to(db_session, course_id=target.id, limit=10) == []


async def test_similar_is_empty_for_a_course_not_embedded_yet(
    db_session: AsyncSession,
) -> None:
    """Published a minute ago, batch has not run. The page shows no block
    rather than an error."""
    target = await add_course(db_session, title="Python cơ bản")
    await add_course(db_session, title="Python nâng cao")

    assert await similar_to(db_session, course_id=target.id, limit=10) == []


async def test_similar_ignores_vectors_from_another_model(
    db_session: AsyncSession,
) -> None:
    """Two models can share a width and disagree about every sentence, so a
    distance between them is a number with no meaning."""
    target = await add_course(db_session, title="Python cơ bản")
    same_model = await add_course(db_session, title="Python nâng cao")
    other_model = await add_course(db_session, title="Python chuyên sâu")
    await rebuild_embeddings(
        db_session,
        embedder=FakeEmbedder({"Python": axis(0)}, model="model-a"),
        course_ids=[target.id, same_model.id],
    )
    await rebuild_embeddings(
        db_session,
        embedder=FakeEmbedder({"Python": axis(0)}, model="model-b"),
        course_ids=[other_model.id],
    )

    found = await similar_to(db_session, course_id=target.id, limit=10)

    assert [item.course.id for item in found] == [same_model.id]


async def test_similar_returns_at_most_the_limit(db_session: AsyncSession) -> None:
    target = await add_course(db_session, title="Python cơ bản")
    others = [
        await add_course(db_session, title=f"Khóa {index}") for index in range(4)
    ]
    await rebuild_embeddings(
        db_session,
        embedder=FakeEmbedder({"Python cơ bản": axis(0)}),
        course_ids=[target.id, *[course.id for course in others]],
    )

    assert len(await similar_to(db_session, course_id=target.id, limit=2)) == 2


async def test_similar_refuses_a_course_the_public_cannot_see(
    db_session: AsyncSession,
) -> None:
    """The block lives on the public course page, so a draft has no answer
    here -- not an empty list, which would read as "nothing is similar"."""
    draft = await add_course(db_session, title="Bản nháp", status="draft")

    with pytest.raises(CourseNotFoundError):
        await similar_to(db_session, course_id=draft.id, limit=10)


async def test_similar_refuses_a_course_that_does_not_exist(
    db_session: AsyncSession,
) -> None:
    with pytest.raises(CourseNotFoundError):
        await similar_to(db_session, course_id=uuid.uuid4(), limit=10)


# --- "Học tiếp theo": the neighbours a reader does not have yet -------------


async def add_reader(session: AsyncSession, *courses: Course) -> User:
    reader = User(
        email=f"hv-{uuid.uuid4().hex[:8]}@example.com",
        full_name="Học viên",
        password_hash=hash_password(PASSWORD),
        role="student",
    )
    session.add(reader)
    await session.flush()
    session.add_all(Enrollment(user_id=reader.id, course_id=c.id) for c in courses)
    await session.flush()
    return reader


async def three_in_a_row(session: AsyncSession) -> tuple[Course, Course, Course]:
    """A target on axis 0, one course 45 degrees off it, one at right angles."""
    target = await add_course(session, title="Python cơ bản")
    near = await add_course(session, title="Python nâng cao")
    far = await add_course(session, title="Thiết kế đồ họa")
    await rebuild_embeddings(
        session,
        embedder=FakeEmbedder(
            {
                "Python cơ bản": axis(0),
                "Python nâng cao": axis(0, 1),
                "Thiết kế đồ họa": axis(5),
            }
        ),
        course_ids=[target.id, near.id, far.id],
    )
    return target, near, far


async def test_similar_can_leave_out_what_the_reader_already_has(
    db_session: AsyncSession,
) -> None:
    """What "Học tiếp theo" is for: the reader finished the target and already
    took the nearest course, so offering it again as "next" is no suggestion."""
    target, near, far = await three_in_a_row(db_session)
    reader = await add_reader(db_session, target, near)

    found = await similar_to(
        db_session, course_id=target.id, limit=10, skip_enrolled_by=reader.id
    )

    assert [item.course.id for item in found] == [far.id]


async def test_leaving_out_the_readers_courses_happens_before_the_limit(
    db_session: AsyncSession,
) -> None:
    """Filtered inside the query, not afterwards. Filtering a `LIMIT 1` answer
    after the fact would drop the one row and hand back an empty block while
    a perfectly good neighbour sat one place further down."""
    target, near, far = await three_in_a_row(db_session)
    reader = await add_reader(db_session, near)

    found = await similar_to(
        db_session, course_id=target.id, limit=1, skip_enrolled_by=reader.id
    )

    assert [item.course.id for item in found] == [far.id]


async def test_somebody_elses_courses_are_not_left_out(
    db_session: AsyncSession,
) -> None:
    target, near, far = await three_in_a_row(db_session)
    await add_reader(db_session, near)
    reader = await add_reader(db_session, target)

    found = await similar_to(
        db_session, course_id=target.id, limit=10, skip_enrolled_by=reader.id
    )

    assert [item.course.id for item in found] == [near.id, far.id]


# --- Recommending from a history -------------------------------------------


def vectors_of(*pairs) -> list[CourseVector]:
    return [CourseVector(course_id=course_id, embedding=vector) for course_id, vector in pairs]


def test_history_recommendations_rank_by_closeness_to_what_the_user_has() -> None:
    """Hand-checkable. The reader has H1 strongly (weight 3) and H2 weakly (1).

        X = e0        → 3·1      + 1·0      = 3,0000
        Y = e0+e1     → 3·0,7071 + 1·0,7071 = 2,8284
        Z = e1        → 3·0      + 1·1      = 1,0000
    """
    found = recommend_from_history(
        vectors_of(
            ("h1", axis(0)),
            ("h2", axis(1)),
            ("x", axis(0)),
            ("y", axis(0, 1)),
            ("z", axis(1)),
        ),
        history={"h1": 3, "h2": 1},
        k=10,
    )

    assert [item.course_id for item in found] == ["x", "y", "z"]
    assert found[0].score == pytest.approx(3.0)
    assert found[1].score == pytest.approx(4 * 2**-0.5)
    assert found[2].score == pytest.approx(1.0)


def test_a_course_the_reader_already_has_is_not_recommended_back() -> None:
    found = recommend_from_history(
        vectors_of(("h1", axis(0)), ("x", axis(0))), history={"h1": 1}, k=10
    )

    assert [item.course_id for item in found] == ["x"]


def test_because_names_the_course_that_contributed_most() -> None:
    """Not merely the nearest one: how strongly the reader took it counts too."""
    found = recommend_from_history(
        vectors_of(("h1", axis(0)), ("h2", axis(0, 1)), ("x", axis(0, 1))),
        history={"h1": 3, "h2": 1},
        k=10,
    )

    # h1 contributes 3 × 0,7071 = 2,12; h2 contributes 1 × 1 = 1.
    assert found[0].because == "h1"


def test_no_history_means_no_content_recommendations() -> None:
    """Cold start belongs to the popularity fallback, not here -- answering it
    with "popular courses" would hide a second model inside this one."""
    assert recommend_from_history(vectors_of(("x", axis(0))), history={}, k=10) == []


def test_a_history_course_with_no_vector_is_skipped_not_fatal() -> None:
    """Published an hour ago, nightly embedding has not run. The reader's other
    courses still say something."""
    found = recommend_from_history(
        vectors_of(("h1", axis(0)), ("x", axis(0))),
        history={"h1": 1, "khong-co-vector": 2},
        k=10,
    )

    assert [item.course_id for item in found] == ["x"]


def test_history_recommendations_stop_at_k() -> None:
    found = recommend_from_history(
        vectors_of(("h1", axis(0)), ("x", axis(0)), ("y", axis(0, 1)), ("z", axis(1))),
        history={"h1": 1},
        k=2,
    )

    assert len(found) == 2


def test_a_candidate_nothing_points_at_is_left_out_rather_than_listed_at_zero() -> None:
    """Same rule as the collaborative half: a recommendation with no reason
    behind it is not a recommendation."""
    found = recommend_from_history(
        vectors_of(("h1", axis(0)), ("x", axis(5))), history={"h1": 1}, k=10
    )

    assert found == []


async def test_load_vectors_reads_only_what_may_be_recommended(
    db_session: AsyncSession,
) -> None:
    """Published, undeleted, and embedded by the model being asked about --
    a distance between two models' vectors is a number with no meaning."""
    published = await add_course(db_session, title="Đã xuất bản")
    draft = await add_course(db_session, title="Bản nháp", status="draft")
    other_model = await add_course(db_session, title="Model khác")
    await rebuild_embeddings(
        db_session,
        embedder=FakeEmbedder(model="model-a"),
        course_ids=[published.id, draft.id],
    )
    await rebuild_embeddings(
        db_session, embedder=FakeEmbedder(model="model-b"), course_ids=[other_model.id]
    )

    loaded = {vector.course_id for vector in await load_vectors(db_session, model="model-a")}

    assert published.id in loaded
    assert draft.id not in loaded
    assert other_model.id not in loaded
