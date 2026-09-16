"""The chunk table, checked against a real Postgres rather than in the abstract.

Everything interesting about `doc_chunks` happens on the server side: the
column type comes from an extension, the width of a vector is enforced by that
extension, and the driver has to carry 768 floats each way without turning them
into a string. None of that is visible to a metadata test -- `test_models`
checks what the model *says*, and this file checks what the database *does*.

The retrieval query the chatbot will run is `ORDER BY embedding <=> :question`,
so that is the query written here, with the same operator class the HNSW index
was built with. A test that ordered by anything else would pass while the real
query silently sequential-scanned.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models import (
    EMBEDDING_DIMENSIONS,
    Category,
    Course,
    CourseSection,
    DocChunk,
    Lesson,
    User,
)

MODEL_NAME = "text-embedding-004"
PASSWORD = "mật-khẩu-đủ-dài"


def axis(*positions: int) -> list[float]:
    """A vector with ones on the given axes and zeros everywhere else.

    Real embeddings are dense and unreadable; these are neither, which is the
    point -- the distance between two of them can be worked out on paper, so a
    wrong answer is wrong for a reason rather than merely different.
    """
    vector = [0.0] * EMBEDDING_DIMENSIONS
    for position in positions:
        vector[position] = 1.0
    return vector


async def make_lesson(db_session: AsyncSession, title: str) -> Lesson:
    """One lesson, with the instructor, category, course and section under it."""
    instructor = User(
        email=f"gv-{uuid.uuid4().hex[:8]}@example.com",
        full_name="Giảng viên",
        password_hash=hash_password(PASSWORD),
        role="instructor",
    )
    category = Category(name="Lập trình", slug=f"lap-trinh-{uuid.uuid4().hex[:8]}")
    db_session.add_all([instructor, category])
    await db_session.flush()

    course = Course(
        instructor_id=instructor.id,
        category_id=category.id,
        title=title,
        slug=f"khoa-hoc-{uuid.uuid4().hex[:8]}",
        price=Decimal("0"),
        status="published",
        published_at=datetime.now(UTC),
    )
    db_session.add(course)
    await db_session.flush()

    section = CourseSection(course_id=course.id, title="Chương 1", position=0)
    db_session.add(section)
    await db_session.flush()

    lesson = Lesson(section_id=section.id, title="Biến và kiểu dữ liệu", type="video", position=0)
    db_session.add(lesson)
    await db_session.flush()
    return lesson


@pytest.fixture
async def lesson(db_session: AsyncSession) -> Lesson:
    return await make_lesson(db_session, "Python cơ bản")


async def course_id_of(db_session: AsyncSession, lesson: Lesson) -> uuid.UUID:
    section = await db_session.get(CourseSection, lesson.section_id)
    return section.course_id


async def add_chunk(
    db_session: AsyncSession,
    lesson: Lesson,
    index: int,
    content: str,
    embedding: list[float],
) -> DocChunk:
    chunk = DocChunk(
        course_id=await course_id_of(db_session, lesson),
        lesson_id=lesson.id,
        chunk_index=index,
        content=content,
        token_count=max(len(content.split()), 1),
        embedding=embedding,
        embedding_model=MODEL_NAME,
    )
    db_session.add(chunk)
    await db_session.flush()
    return chunk


async def test_an_embedding_comes_back_the_way_it_went_in(
    db_session: AsyncSession, lesson: Lesson
):
    """768 floats, through asyncpg, unchanged.

    This is the test that catches the failure mode people hit when wiring
    pgvector to an async driver: a vector that arrives as the *text* of a list
    still stores and still compares, and every distance computed from it is
    quietly wrong.
    """
    written = axis(0, 5, 767)
    chunk = await add_chunk(db_session, lesson, 0, "Biến trong Python", written)

    read_back = (
        await db_session.execute(select(DocChunk).where(DocChunk.id == chunk.id))
    ).scalar_one()

    assert list(read_back.embedding) == written
    assert len(read_back.embedding) == EMBEDDING_DIMENSIONS
    assert read_back.embedding_model == MODEL_NAME


async def test_the_nearest_chunk_comes_back_first(
    db_session: AsyncSession, lesson: Lesson
):
    """The retrieval the chatbot depends on, in miniature.

    Cosine distance of a vector to itself is 0, to a 45-degree neighbour
    1 - sqrt(2)/2 = 0.293, and to a perpendicular one exactly 1. Asserting the
    numbers and not only the order is what pins the operator to cosine: L2
    distance would rank these three identically and report different numbers.
    """
    await add_chunk(db_session, lesson, 0, "đúng chủ đề", axis(0))
    await add_chunk(db_session, lesson, 1, "liên quan một nửa", axis(0, 1))
    await add_chunk(db_session, lesson, 2, "chủ đề khác", axis(1))

    question = axis(0)
    ranked = (
        await db_session.execute(
            select(
                DocChunk.content,
                DocChunk.embedding.cosine_distance(question).label("distance"),
            )
            .where(DocChunk.lesson_id == lesson.id)
            .order_by(DocChunk.embedding.cosine_distance(question))
        )
    ).all()

    assert [row.content for row in ranked] == [
        "đúng chủ đề",
        "liên quan một nửa",
        "chủ đề khác",
    ]
    assert [round(float(row.distance), 3) for row in ranked] == [0.0, 0.293, 1.0]


async def test_retrieval_stays_inside_one_course(db_session: AsyncSession, lesson: Lesson):
    """The scope rule, enforced by the query rather than by the prompt.

    The other course's chunk is a perfect match for the question and must still
    not come back: "chỉ trả lời trong phạm vi khóa học" is a filter on rows,
    because a promise made only in the prompt is a promise the model can break.
    """
    elsewhere = await make_lesson(db_session, "Khóa học khác")
    await add_chunk(db_session, elsewhere, 0, "khóa học khác", axis(0))
    await add_chunk(db_session, lesson, 0, "khóa học này", axis(0, 1))

    question = axis(0)
    course_id = await course_id_of(db_session, lesson)
    found = (
        (
            await db_session.execute(
                select(DocChunk.content)
                .where(DocChunk.course_id == course_id)
                .order_by(DocChunk.embedding.cosine_distance(question))
                .limit(3)
            )
        )
        .scalars()
        .all()
    )

    assert list(found) == ["khóa học này"]


async def test_the_same_slot_of_a_lesson_cannot_be_filled_twice(
    db_session: AsyncSession, lesson: Lesson
):
    """Re-ingest deletes and rewrites; a half-finished one must not double up."""
    await add_chunk(db_session, lesson, 0, "đoạn thứ nhất", axis(0))

    with pytest.raises(IntegrityError):
        await add_chunk(db_session, lesson, 0, "cũng là đoạn thứ nhất", axis(1))
    await db_session.rollback()


async def test_a_vector_of_the_wrong_width_is_refused(
    db_session: AsyncSession, lesson: Lesson
):
    """The day the embedding model changes, this is the error we want.

    Not a silent truncation, and not a row that stores fine and ranks wrongly:
    a refusal from Postgres that names both widths.
    """
    with pytest.raises(DBAPIError) as raised:
        await add_chunk(db_session, lesson, 0, "quá ngắn", [1.0, 2.0, 3.0])

    assert "expected 768 dimensions" in str(raised.value.orig)
    await db_session.rollback()


async def test_an_empty_chunk_is_refused(db_session: AsyncSession, lesson: Lesson):
    """An empty chunk is a citation with nothing to quote."""
    with pytest.raises(IntegrityError):
        await add_chunk(db_session, lesson, 0, "", axis(0))
    await db_session.rollback()


async def test_deleting_the_lesson_takes_its_chunks_with_it(
    db_session: AsyncSession, lesson: Lesson
):
    """Deleting content must not leave the assistant quoting it."""
    await add_chunk(db_session, lesson, 0, "nội dung bài học", axis(0))

    await db_session.delete(lesson)
    await db_session.flush()

    remaining = (
        await db_session.execute(
            select(func.count()).select_from(DocChunk).where(DocChunk.lesson_id == lesson.id)
        )
    ).scalar_one()
    assert remaining == 0
