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

**Video lessons are read from their transcript**, which lives in the bucket
(`video_assets.transcript_key`, uploaded through `services/transcripts.py`) and
is fetched back here, parsed by the same function that checked it on upload.
A transcript that exists but cannot be read on this run -- the bucket blinked,
or the worker has no bucket credentials -- is **not** a lesson without text:
its chunks stay as they were and the lesson is counted `unreadable`. Treating
it as empty would wipe the chatbot's memory of every video on a network hiccup,
and paying the embedding quota again to refill it.

**A lesson with no text has no chunks either.** Emptying an article, or
turning it into a video with no transcript yet, removes its rows on the next
run -- otherwise the assistant would keep citing words the lesson no longer
has. Unpublishing a course does *not* remove its chunks: publishing it again
would pay for every embedding a second time. Keeping an unpublished course's
chunks out of answers is the retrieval query's job (filter on the course being
published and the asker being enrolled), not this module's.
"""

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models import Course, CourseSection, DocChunk, Lesson
from app.services.chunking import chunk_text
from app.services.llm import Embedder
from app.services.storage import ObjectStorage
from app.services.transcripts import format_of_key, transcript_text

logger = logging.getLogger(__name__)


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
    #: Of the skipped, lessons that still had chunks from an earlier run --
    #: text since emptied -- and lost them in this one.
    removed: int = 0
    #: Videos whose transcript exists but could not be fetched or parsed this
    #: time. Their chunks are left exactly as they were; run again later.
    unreadable: int = 0


class TranscriptUnavailable(Exception):
    """A lesson has a transcript, and this run could not read it."""


def transcript_of(lesson: Lesson, storage: ObjectStorage | None) -> str | None:
    """A video lesson's transcript as plain words, or None if it has none.

    Raises TranscriptUnavailable when there is one but it cannot be read now --
    which the caller must tell apart from "none", see the module docstring.
    """
    asset = lesson.video_asset
    if lesson.type != "video" or asset is None or asset.transcript_key is None:
        return None
    if storage is None:
        raise TranscriptUnavailable("không có kho lưu trữ để đọc transcript")

    key = asset.transcript_key
    try:
        raw = storage.read_bytes(key).decode("utf-8")
        return transcript_text(raw, format_of_key(key))
    except Exception as exc:
        raise TranscriptUnavailable(f"{key}: {exc}") from exc


def lesson_text(lesson: Lesson, transcript: str | None = None) -> str:
    """The words of a lesson, or empty if it has none.

    An article's are its content; a video's are its transcript, which the
    caller fetched (`transcript_of`) because reading it is IO.

    The title is prepended rather than left in the `lessons` row: retrieval
    compares a question against the chunk's own text, so a chunk that never
    names its subject can only be found through whatever words happen to fall
    inside it. It costs a few tokens per chunk and buys every chunk a heading.
    """
    if lesson.type == "article":
        body = (lesson.article_content or "").strip()
    elif lesson.type == "video":
        body = (transcript or "").strip()
    else:
        body = ""
    return f"{lesson.title}\n\n{body}" if body else ""


async def ingest_course(
    session: AsyncSession,
    course_id: uuid.UUID,
    *,
    embedder: Embedder,
    storage: ObjectStorage | None = None,
) -> IngestReport:
    """Chunk, embed and store every lesson of one course.

    `storage` is where transcripts are read from; without one, every video that
    has a transcript is `unreadable` and keeps whatever chunks it had.

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

    lessons_done = chunks_written = unchanged = skipped = removed = unreadable = 0

    for lesson in lessons:
        try:
            transcript = transcript_of(lesson, storage)
        except TranscriptUnavailable as error:
            logger.warning("Không đọc được transcript bài %s: %s", lesson.id, error)
            unreadable += 1
            continue

        text = lesson_text(lesson, transcript)
        chunks = chunk_text(text) if text else []
        if not chunks:
            skipped += 1
            # No text now does not mean there never was any. Rows from an
            # earlier run would stay retrievable, quoting a lesson that no
            # longer says any of it -- so a lesson with nothing to ingest is
            # also a lesson with nothing in the index.
            gone = await session.execute(
                delete(DocChunk).where(DocChunk.lesson_id == lesson.id)
            )
            if gone.rowcount:
                removed += 1
                await session.commit()
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
        removed=removed,
        unreadable=unreadable,
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
