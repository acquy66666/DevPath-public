"""Turning a course's lessons into rows the chatbot can retrieve.

The embedder is a fake here, and deliberately: what these tests are about is
which lessons become chunks, what those rows contain, and what happens on the
second run. Whether Gemini returns good vectors is a question for the live
probe in `docs/report/assets/phase-4/embedding-model.txt`; whether this code
writes the wrong `course_id` is a question for here, and a live call would
answer it no better while costing quota.

Re-ingest is the case with the most tests behind it. Publishing a course is a
button an instructor can press repeatedly, and the plan names Gemini quota as
a live project risk -- so "publish twice, pay twice" is a bug worth catching
before it is a bill.
"""

import hashlib
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models import Category, Course, CourseSection, DocChunk, Lesson, User
from app.models.rag import EMBEDDING_DIMENSIONS
from app.services.chunking import chunk_text
from app.services.ingest import ingest_course
from app.services.llm import LLMUnavailableError

LONG_ARTICLE = "\n\n".join(
    f"Đoạn số {index}. Trong phần {index}, biến được tạo ra ngay khi bạn gán "
    f"giá trị cho nó bằng dấu bằng. Ở mục {index} không cần khai báo kiểu "
    f"trước khi dùng, và kiểu của một biến có thể thay đổi về sau."
    for index in range(30)
)
SHORT_ARTICLE = "Vòng lặp for duyệt qua từng phần tử của một danh sách."


class FakeEmbedder:
    """Deterministic vectors, and a record of what it was asked to embed."""

    def __init__(self, *, model: str = "fake-embedding-001") -> None:
        self._model = model
        self.calls: list[list[str]] = []

    @property
    def model(self) -> str:
        return self._model

    async def embed_documents(self, texts) -> list[list[float]]:
        texts = list(texts)
        self.calls.append(texts)
        return [self._vector(text) for text in texts]

    async def embed_query(self, text: str) -> list[float]:
        return self._vector(text)

    @staticmethod
    def _vector(text: str) -> list[float]:
        digest = hashlib.sha256(text.encode()).digest()
        raw = [digest[index % len(digest)] / 255 for index in range(EMBEDDING_DIMENSIONS)]
        norm = sum(value * value for value in raw) ** 0.5
        return [value / norm for value in raw]


class BrokenEmbedder(FakeEmbedder):
    """Runs out of quota on the nth call, like a free-tier key does."""

    def __init__(self, *, fail_after: int) -> None:
        super().__init__()
        self._fail_after = fail_after

    async def embed_documents(self, texts):
        if len(self.calls) >= self._fail_after:
            raise LLMUnavailableError("Gọi Gemini thất bại (HTTP 429: quota)")
        return await super().embed_documents(texts)


@pytest.fixture
async def course(db_session: AsyncSession) -> Course:
    """A course with one lesson of every type, only one of which has text."""
    instructor = User(
        email=f"gv-{uuid.uuid4().hex[:8]}@example.com",
        full_name="Giảng viên",
        password_hash="x",
        role="instructor",
    )
    category = Category(name="Lập trình", slug=f"lt-{uuid.uuid4().hex[:8]}")
    db_session.add_all([instructor, category])
    await db_session.flush()

    course = Course(
        instructor_id=instructor.id,
        category_id=category.id,
        title="Khóa thử",
        slug=f"khoa-thu-{uuid.uuid4().hex[:8]}",
        status="draft",
    )
    db_session.add(course)
    await db_session.flush()

    section = CourseSection(course_id=course.id, title="Chương 1", position=0)
    db_session.add(section)
    await db_session.flush()

    db_session.add_all(
        [
            Lesson(
                section_id=section.id,
                title="Biến trong Python",
                type="article",
                position=0,
                article_content=LONG_ARTICLE,
            ),
            Lesson(section_id=section.id, title="Video bài giảng", type="video", position=1),
            Lesson(section_id=section.id, title="Bài kiểm tra", type="quiz", position=2),
            Lesson(
                section_id=section.id, title="Bài tập", type="code_exercise", position=3
            ),
        ]
    )
    await db_session.flush()
    return course


async def article_lesson(session: AsyncSession, course_id: uuid.UUID) -> Lesson:
    """The fixture's own article lesson.

    Scoped to the course on purpose. A plain `select(Lesson).where(type ==
    "article")` finds whatever the seeded catalogue put in the database first,
    and five tests in this file passed or failed depending on which machine
    they ran on before this helper existed.
    """
    return await session.scalar(
        select(Lesson)
        .join(CourseSection, CourseSection.id == Lesson.section_id)
        .where(CourseSection.course_id == course_id, Lesson.type == "article")
        .order_by(Lesson.position)
    )


async def section_of(session: AsyncSession, course_id: uuid.UUID) -> CourseSection:
    return await session.scalar(
        select(CourseSection).where(CourseSection.course_id == course_id)
    )


async def chunks_of(session: AsyncSession, course_id: uuid.UUID) -> list[DocChunk]:
    return list(
        await session.scalars(
            select(DocChunk)
            .where(DocChunk.course_id == course_id)
            .order_by(DocChunk.chunk_index)
        )
    )


async def test_only_lessons_that_have_text_are_ingested(
    db_session: AsyncSession, course: Course
) -> None:
    """A video with no transcript, a quiz and an exercise have nothing to
    chunk. Writing a row for them would put the embedding of a lesson title
    into the index, and a title matches every question about its topic while
    answering none of them."""
    embedder = FakeEmbedder()

    report = await ingest_course(db_session, course.id, embedder=embedder)

    assert report.lessons == 1
    assert report.skipped == 3
    assert report.chunks == len(await chunks_of(db_session, course.id))
    assert report.chunks > 1, "the fixture article is long enough to split"


async def test_a_chunk_row_carries_everything_a_citation_needs(
    db_session: AsyncSession, course: Course
) -> None:
    embedder = FakeEmbedder()
    await ingest_course(db_session, course.id, embedder=embedder)

    rows = await chunks_of(db_session, course.id)
    lesson = await article_lesson(db_session, course.id)

    assert [row.chunk_index for row in rows] == list(range(len(rows)))
    for row in rows:
        assert row.course_id == course.id
        assert row.lesson_id == lesson.id
        assert row.content.strip() == row.content and row.content
        assert row.token_count > 0
        assert len(row.embedding) == EMBEDDING_DIMENSIONS
        assert row.embedding_model == embedder.model


async def test_the_lesson_title_travels_with_its_text(
    db_session: AsyncSession, course: Course
) -> None:
    """Retrieval matches a question against the chunk, not against the lesson
    row it hangs off, so a chunk that never names its subject can only be
    found by the words that happen to be inside it."""
    await ingest_course(db_session, course.id, embedder=FakeEmbedder())

    rows = await chunks_of(db_session, course.id)
    assert "Biến trong Python" in rows[0].content


async def test_ingesting_an_unchanged_course_again_costs_no_quota(
    db_session: AsyncSession, course: Course
) -> None:
    """The publish button can be pressed twice. The second press must not buy
    the same vectors again."""
    embedder = FakeEmbedder()
    first = await ingest_course(db_session, course.id, embedder=embedder)
    calls_after_first = len(embedder.calls)

    second = await ingest_course(db_session, course.id, embedder=embedder)

    assert calls_after_first > 0
    assert len(embedder.calls) == calls_after_first, "embedded the same text twice"
    assert second.chunks == 0
    assert second.unchanged == first.lessons
    assert len(await chunks_of(db_session, course.id)) == first.chunks


async def test_editing_a_lesson_replaces_its_chunks(
    db_session: AsyncSession, course: Course
) -> None:
    await ingest_course(db_session, course.id, embedder=FakeEmbedder())
    before = await chunks_of(db_session, course.id)

    lesson = await article_lesson(db_session, course.id)
    lesson.article_content = SHORT_ARTICLE
    await db_session.flush()

    report = await ingest_course(db_session, course.id, embedder=FakeEmbedder())
    after = await chunks_of(db_session, course.id)

    assert report.chunks == len(after)
    # Shorter text, fewer chunks -- and no orphans left behind at the indexes
    # the old version used, which `uq_doc_chunks_lesson_chunk` would not catch
    # because those indexes are simply never written again.
    assert len(after) < len(before)
    assert [row.chunk_index for row in after] == list(range(len(after)))
    assert SHORT_ARTICLE in after[0].content


async def test_the_rows_match_what_the_chunker_produced(
    db_session: AsyncSession, course: Course
) -> None:
    """Guards the seam between chunking and storage: a slice done twice, an
    off-by-one in the index, a strip() applied on one side only."""
    await ingest_course(db_session, course.id, embedder=FakeEmbedder())

    lesson = await article_lesson(db_session, course.id)
    expected = chunk_text(f"{lesson.title}\n\n{lesson.article_content}")
    rows = await chunks_of(db_session, course.id)

    assert [row.content for row in rows] == [chunk.content for chunk in expected]
    assert [row.token_count for row in rows] == [chunk.token_count for chunk in expected]


async def test_a_course_with_nothing_to_ingest_reports_so(
    db_session: AsyncSession, course: Course
) -> None:
    lesson = await article_lesson(db_session, course.id)
    lesson.article_content = "   "
    await db_session.flush()

    report = await ingest_course(db_session, course.id, embedder=FakeEmbedder())

    assert (report.lessons, report.chunks) == (0, 0)
    assert report.skipped == 4
    assert await chunks_of(db_session, course.id) == []


async def test_a_lesson_that_loses_its_text_loses_its_chunks(
    db_session: AsyncSession, course: Course
) -> None:
    """An emptied article must stop being something the chatbot can quote.

    Before this, a lesson with no text was only counted as skipped, and the
    rows from its last ingest stayed in the index -- retrievable, citing a
    lesson that no longer says any of it.
    """
    await ingest_course(db_session, course.id, embedder=FakeEmbedder())
    assert await chunks_of(db_session, course.id), "the article was ingested first"

    lesson = await article_lesson(db_session, course.id)
    lesson.article_content = ""
    await db_session.flush()

    report = await ingest_course(db_session, course.id, embedder=FakeEmbedder())

    assert await chunks_of(db_session, course.id) == []
    assert report.removed == 1
    assert report.skipped == 4


async def test_only_lessons_that_had_chunks_are_counted_as_removed(
    db_session: AsyncSession, course: Course
) -> None:
    """The video, the quiz and the exercise never had rows to lose.

    `removed` says how much the index shrank. Counting every skipped lesson
    would report a deletion on every run of every course.
    """
    report = await ingest_course(db_session, course.id, embedder=FakeEmbedder())

    assert report.skipped == 3
    assert report.removed == 0


async def test_running_out_of_quota_keeps_what_was_already_ingested(
    db_session: AsyncSession, course: Course
) -> None:
    """A course is ingested lesson by lesson and committed lesson by lesson,
    so a key that dies halfway leaves the first half searchable and the job
    re-runnable -- rather than nothing, twice."""
    section = await section_of(db_session, course.id)
    db_session.add(
        Lesson(
            section_id=section.id,
            title="Bài thứ hai",
            type="article",
            position=4,
            article_content=LONG_ARTICLE,
        )
    )
    await db_session.flush()

    with pytest.raises(LLMUnavailableError):
        await ingest_course(db_session, course.id, embedder=BrokenEmbedder(fail_after=1))

    rows = await chunks_of(db_session, course.id)
    assert rows, "the lesson embedded before the failure should have survived"
    assert len({row.lesson_id for row in rows}) == 1


async def test_ingesting_a_course_that_is_not_there(db_session: AsyncSession) -> None:
    with pytest.raises(NotFoundError):
        await ingest_course(db_session, uuid.uuid4(), embedder=FakeEmbedder())


async def test_a_deleted_course_is_not_ingested(
    db_session: AsyncSession, course: Course
) -> None:
    """Soft-deleted courses are invisible everywhere else; embedding one would
    make it answerable by a chatbot that no page links to."""
    from datetime import UTC, datetime

    course.deleted_at = datetime.now(UTC)
    await db_session.flush()

    with pytest.raises(NotFoundError):
        await ingest_course(db_session, course.id, embedder=FakeEmbedder())


async def test_switching_embedding_model_re_embeds_everything(
    db_session: AsyncSession, course: Course
) -> None:
    """Two models can share a width and still put the same sentence somewhere
    else entirely. A table holding both returns nonsense rather than an error,
    so a changed model name is a reason to redo the work even when the text is
    identical -- which is exactly what `embedding_model` is stored for."""
    await ingest_course(db_session, course.id, embedder=FakeEmbedder())

    newer = FakeEmbedder(model="fake-embedding-002")
    report = await ingest_course(db_session, course.id, embedder=newer)

    assert report.chunks > 0
    assert newer.calls, "should have paid for new vectors"
    rows = await chunks_of(db_session, course.id)
    assert {row.embedding_model for row in rows} == {"fake-embedding-002"}
