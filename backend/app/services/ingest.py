"""Filling `doc_chunks` from a course's own lessons.

This is the half of the RAG pipeline that runs when nobody is watching: a
course is published, a Celery job walks its lessons, and every passage of text
becomes a row the chatbot can later find and quote. Everything the assistant is
allowed to say is decided here -- it answers from these rows and nothing else,
so a lesson that never got ingested is a lesson the assistant will claim to
know nothing about.

**Lesson by lesson, committed lesson by lesson.** A course is dozens of
embedding calls on a key that the plan already names as a quota risk. Doing the
whole course in one transaction would mean a key that dies two-thirds of the
way through leaves nothing behind and the next run starts from zero. Committing
as it goes means a failure is resumable, and the re-ingest check below makes
resuming cheap.

**Re-ingest is free when nothing changed.** Publish is a button, and an
instructor may press it after every edit. Comparing the chunks a lesson *would*
produce against the rows it already has costs one query and saves the entire
embedding bill for a republish that changed a typo in a different lesson. The
comparison includes the model name, because a vector is only comparable with
others from the same model.

Video transcripts are not here yet. `video_assets.transcript_key` points into
R2, so reading one needs the storage client and an upload route for instructors
to put a `.srt` there -- the next task. `_lesson_text` is the single place that
decides what a lesson's words are, so that task adds a branch to one function.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models import Course, CourseSection, DocChunk, Lesson
from app.services.chunking import chunk_text
from app.services.llm import Embedder


@dataclass(frozen=True, slots=True)
class IngestReport:
    """What one run did. Printed by the script, logged by the worker."""

    #: Lessons whose chunks were written or rewritten.
    lessons: int
    #: Rows written. Zero with `unchanged > 0` means everything was up to date.
    chunks: int
    #: Lessons already ingested with the same text and the same model.
    unchanged: int
    #: Lessons with no text to ingest -- video without a transcript, quizzes,
    #: exercises. Not a failure; the number is here so a course that ingested
    #: nothing can be told apart from a course that has nothing to ingest.
    skipped: int


def _lesson_text(lesson: Lesson) -> str:
    """The words of a lesson, or empty if it has none.

    The title is prepended rather than left in the `lessons` row: retrieval
    compares a question against the chunk's own text, so a chunk that never
    names its subject can only be found through whatever words happen to fall
    inside it. It costs a few tokens per chunk and buys every chunk a heading.
    """
    if lesson.type == "article" and lesson.article_content:
        body = lesson.article_content.strip()
        if body:
            return f"{lesson.title}\n\n{body}"
    return ""


async def ingest_course(
    session: AsyncSession, course_id: uuid.UUID, *, embedder: Embedder
) -> IngestReport:
    """Chunk, embed and store every lesson of one course.

    Raises whatever the embedder raises. The caller -- a Celery task -- turns
    that into a retry; the lessons already committed stay committed.
    """
    course = await session.scalar(
        select(Course).where(Course.id == course_id, Course.deleted_at.is_(None))
    )
    if course is None:
        raise NotFoundError("Không tìm thấy khóa học để nạp dữ liệu")

    lessons = list(
        await session.scalars(
            select(Lesson)
            .join(CourseSection, CourseSection.id == Lesson.section_id)
            .where(CourseSection.course_id == course_id)
            .order_by(CourseSection.position, Lesson.position)
        )
    )

    lessons_done = chunks_written = unchanged = skipped = 0

    for lesson in lessons:
        text = _lesson_text(lesson)
        if not text:
            skipped += 1
            continue

        chunks = chunk_text(text)
        if not chunks:
            skipped += 1
            continue

        existing = list(
            await session.scalars(
                select(DocChunk)
                .where(DocChunk.lesson_id == lesson.id)
                .order_by(DocChunk.chunk_index)
            )
        )
        if _already_current(existing, chunks, embedder.model):
            unchanged += 1
            continue

        vectors = await embedder.embed_documents([chunk.content for chunk in chunks])

        # Delete and rewrite rather than update in place: the new text may
        # produce fewer chunks than the old, and the rows at the indexes that
        # no longer exist would otherwise stay behind, retrievable, quoting a
        # version of the lesson nobody can read any more.
        await session.execute(delete(DocChunk).where(DocChunk.lesson_id == lesson.id))
        session.add_all(
            DocChunk(
                course_id=course_id,
                lesson_id=lesson.id,
                chunk_index=chunk.index,
                content=chunk.content,
                token_count=chunk.token_count,
                embedding=vector,
                embedding_model=embedder.model,
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        )
        await session.commit()

        lessons_done += 1
        chunks_written += len(chunks)

    return IngestReport(
        lessons=lessons_done,
        chunks=chunks_written,
        unchanged=unchanged,
        skipped=skipped,
    )


def _already_current(existing: list[DocChunk], chunks: list, model: str) -> bool:
    """Whether the rows on hand are exactly what this text and model produce."""
    if len(existing) != len(chunks):
        return False
    return all(
        row.chunk_index == chunk.index
        and row.content == chunk.content
        and row.embedding_model == model
        for row, chunk in zip(existing, chunks, strict=True)
    )
