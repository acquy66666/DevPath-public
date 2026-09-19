"""Which passages the course assistant is allowed to read for one question.

This is the privacy boundary of the chatbot, so it is tested at the query and
not only at the endpoint. The endpoint refuses an unenrolled student before it
ever gets here; these tests prove that even a caller who skipped that check
would get nothing back. Unpublishing a course deliberately leaves its chunks
in the table (republishing would otherwise pay for every embedding again), so
the filter below is the *only* thing keeping an unpublished course out of
answers -- see `docs/plan/don-no-2026-09-18.md`, Phiên 4.

Vectors are built by hand at known angles from the question, so "nearest
first" is a fact of trigonometry here rather than of whatever a fake embedder
happened to hash a sentence to.
"""

import math
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Category,
    Course,
    CourseSection,
    DocChunk,
    Enrollment,
    Lesson,
    User,
)
from app.models.rag import EMBEDDING_DIMENSIONS
from app.services.chat import RetrievedChunk, group_sources, merge_hits, retrieve

MODEL = "fake-embedding-001"


def at_angle(degrees: float) -> list[float]:
    """A unit vector `degrees` away from `QUESTION`: cosine = cos(degrees)."""
    radians = math.radians(degrees)
    vector = [0.0] * EMBEDDING_DIMENSIONS
    vector[0] = math.cos(radians)
    vector[1] = math.sin(radians)
    return vector


QUESTION = at_angle(0)


async def make_user(session: AsyncSession, role: str = "student") -> User:
    user = User(
        email=f"{role}-{uuid.uuid4().hex[:8]}@example.com",
        full_name=role.title(),
        password_hash="x",
        role=role,
    )
    session.add(user)
    await session.flush()
    return user


async def make_course(
    session: AsyncSession,
    instructor: User,
    *,
    status: str = "published",
    chunks: list[tuple[str, float]],
    model: str = MODEL,
) -> Course:
    """A course with one lesson per chunk, each chunk at the given angle."""
    category = Category(name="Lập trình", slug=f"lt-{uuid.uuid4().hex[:8]}")
    session.add(category)
    await session.flush()

    course = Course(
        instructor_id=instructor.id,
        category_id=category.id,
        title=f"Khóa {uuid.uuid4().hex[:6]}",
        slug=f"khoa-{uuid.uuid4().hex[:8]}",
        status=status,
        published_at=datetime.now(UTC) if status == "published" else None,
    )
    session.add(course)
    await session.flush()

    section = CourseSection(course_id=course.id, title="Chương 1", position=0)
    session.add(section)
    await session.flush()

    for position, (text, angle) in enumerate(chunks):
        lesson = Lesson(
            section_id=section.id,
            title=f"Bài {text}",
            type="article",
            position=position,
            article_content=text,
        )
        session.add(lesson)
        await session.flush()
        session.add(
            DocChunk(
                course_id=course.id,
                lesson_id=lesson.id,
                chunk_index=0,
                content=text,
                token_count=10,
                embedding=at_angle(angle),
                embedding_model=model,
            )
        )
    await session.flush()
    return course


async def enrol(session: AsyncSession, user: User, course: Course) -> None:
    session.add(Enrollment(user_id=user.id, course_id=course.id))
    await session.flush()


@pytest.fixture
async def instructor(db_session: AsyncSession) -> User:
    return await make_user(db_session, "instructor")


@pytest.fixture
async def student(db_session: AsyncSession) -> User:
    return await make_user(db_session)


async def ask(
    session: AsyncSession, course: Course, user: User, *, k: int = 5, model: str = MODEL
) -> list[RetrievedChunk]:
    return await retrieve(
        session,
        course_id=course.id,
        user_id=user.id,
        query_vector=QUESTION,
        embedding_model=model,
        k=k,
    )


async def test_nearest_passages_come_first_with_their_similarity(
    db_session: AsyncSession, instructor: User, student: User
) -> None:
    course = await make_course(
        db_session, instructor, chunks=[("xa", 60), ("gần", 10), ("vừa", 30)]
    )
    await enrol(db_session, student, course)

    found = await ask(db_session, course, student)

    assert [chunk.content for chunk in found] == ["gần", "vừa", "xa"]
    assert found[0].score == pytest.approx(math.cos(math.radians(10)), abs=1e-4)
    assert found[0].lesson_title == "Bài gần"
    assert found[0].section_title == "Chương 1"


async def test_k_caps_how_many_passages_come_back(
    db_session: AsyncSession, instructor: User, student: User
) -> None:
    course = await make_course(
        db_session, instructor, chunks=[(f"đoạn {i}", i * 5) for i in range(8)]
    )
    await enrol(db_session, student, course)

    found = await ask(db_session, course, student, k=3)

    assert [chunk.content for chunk in found] == ["đoạn 0", "đoạn 1", "đoạn 2"]


async def test_another_course_is_never_quoted_even_when_it_is_closer(
    db_session: AsyncSession, instructor: User, student: User
) -> None:
    """The student is enrolled in both, and the other course holds the better
    match. Still not quoted: the conversation is about this course."""
    course = await make_course(db_session, instructor, chunks=[("của khóa này", 40)])
    other = await make_course(db_session, instructor, chunks=[("khóa khác", 0)])
    await enrol(db_session, student, course)
    await enrol(db_session, student, other)

    found = await ask(db_session, course, student)

    assert [chunk.content for chunk in found] == ["của khóa này"]


async def test_a_student_who_is_not_enrolled_gets_nothing(
    db_session: AsyncSession, instructor: User, student: User
) -> None:
    course = await make_course(db_session, instructor, chunks=[("bài giảng", 0)])

    assert await ask(db_session, course, student) == []


async def test_the_instructor_is_not_an_enrolled_student_either(
    db_session: AsyncSession, instructor: User
) -> None:
    """The rule is "enrolled", as the plan wrote it -- owning the course is
    not a way around it. An instructor cannot enrol in their own course, so
    this is also why the assistant is a student-only feature."""
    course = await make_course(db_session, instructor, chunks=[("bài giảng", 0)])

    assert await ask(db_session, course, instructor) == []


@pytest.mark.parametrize("status", ["draft", "pending_review", "rejected"])
async def test_a_course_that_is_not_published_is_not_quoted(
    db_session: AsyncSession, instructor: User, student: User, status: str
) -> None:
    """Enrolled, chunks present -- and unpublished since. This is the case
    the ingest job leaves behind on purpose, and the reason this filter is
    mandatory."""
    course = await make_course(db_session, instructor, chunks=[("bài giảng", 0)])
    await enrol(db_session, student, course)
    course.status = status
    if status == "rejected":
        course.rejection_reason = "Thiếu nội dung"
    await db_session.flush()

    assert await ask(db_session, course, student) == []


async def test_a_deleted_course_is_not_quoted(
    db_session: AsyncSession, instructor: User, student: User
) -> None:
    course = await make_course(db_session, instructor, chunks=[("bài giảng", 0)])
    await enrol(db_session, student, course)
    course.deleted_at = datetime.now(UTC)
    await db_session.flush()

    assert await ask(db_session, course, student) == []


async def test_vectors_from_another_embedding_model_are_ignored(
    db_session: AsyncSession, instructor: User, student: User
) -> None:
    """Two models can share a width and still place the same sentence in
    different places; comparing across them returns confident nonsense."""
    course = await make_course(
        db_session, instructor, chunks=[("model cũ", 0)], model="old-model"
    )
    await enrol(db_session, student, course)

    assert await ask(db_session, course, student) == []


def chunk(lesson: uuid.UUID, title: str, index: int, score: float) -> RetrievedChunk:
    return RetrievedChunk(
        lesson_id=lesson,
        lesson_title=title,
        section_title="Chương 1",
        chunk_index=index,
        content=f"{title} #{index}",
        score=score,
    )


def test_sources_are_numbered_per_lesson_in_order_of_best_match() -> None:
    """A citation points at a lesson, so two passages of one lesson are one
    source -- read in the order the lesson has them, not the order they
    scored in."""
    first, second = uuid.uuid4(), uuid.uuid4()
    sources = group_sources(
        [
            chunk(second, "Vòng lặp", 3, 0.91),
            chunk(first, "Biến", 0, 0.88),
            chunk(second, "Vòng lặp", 1, 0.80),
        ]
    )

    assert [(s.number, s.lesson_id) for s in sources] == [(1, second), (2, first)]
    assert sources[0].passages == ["Vòng lặp #1", "Vòng lặp #3"]
    assert sources[0].score == pytest.approx(0.91)


def test_no_passages_means_no_sources() -> None:
    assert group_sources([]) == []


def test_two_searches_merge_by_the_better_score_of_each_passage() -> None:
    """A follow-up is searched twice -- alone and with the question before it.
    A passage found by both keeps its better score, and the merged list is cut
    back to k, best first."""
    lesson_a, lesson_b, lesson_c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    alone = [chunk(lesson_a, "A", 0, 0.70), chunk(lesson_b, "B", 0, 0.60)]
    with_previous = [chunk(lesson_c, "C", 0, 0.80), chunk(lesson_a, "A", 0, 0.65)]

    merged = merge_hits([alone, with_previous], k=2)

    assert [(hit.lesson_title, hit.score) for hit in merged] == [("C", 0.80), ("A", 0.70)]


def test_one_search_merges_to_itself() -> None:
    hits = [chunk(uuid.uuid4(), "A", 0, 0.9), chunk(uuid.uuid4(), "B", 1, 0.5)]

    assert merge_hits([hits], k=5) == hits
