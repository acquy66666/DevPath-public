"""Notes and bookmarks: what a student leaves in a lesson for themselves.

Who may write one is not a new rule. It is the rule that already decides who
may *read* the lesson -- owner, preview, or enrolled -- so annotating goes
through `curriculum.get_lesson_for_viewer` and inherits it. Somebody taking
notes on the free sample lesson is fine; somebody taking notes on a lesson they
cannot open is not a case that needs its own answer.

A note that is not yours is answered 404 rather than 403. There is nothing to
gain from confirming that someone else's note exists.
"""

import uuid

from fastapi import status
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DomainError
from app.models import Bookmark, CourseSection, Lesson, Note, User
from app.services import courses as courses_service
from app.services import curriculum as curriculum_service


class NoteNotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "NOTE_NOT_FOUND"


async def _readable_lesson(
    session: AsyncSession, lesson_id: uuid.UUID, user: User
) -> Lesson:
    """A lesson this person may open -- which is a lesson they may annotate."""
    return await curriculum_service.get_lesson_for_viewer(session, lesson_id, user)


async def _own_note(session: AsyncSession, note_id: uuid.UUID, user: User) -> Note:
    note = await session.get(Note, note_id)
    if note is None or note.user_id != user.id:
        raise NoteNotFoundError("Không tìm thấy ghi chú")
    return note


# --- Notes -----------------------------------------------------------------


async def list_notes(
    session: AsyncSession, lesson_id: uuid.UUID, user: User
) -> list[Note]:
    """The caller's notes on one lesson, in the order they happen in the video."""
    await _readable_lesson(session, lesson_id, user)

    rows = await session.scalars(
        select(Note)
        .where(Note.user_id == user.id, Note.lesson_id == lesson_id)
        # `created_at` breaks the tie, and the id breaks that: two notes at the
        # same second of the same video would otherwise come back in whatever
        # order Postgres felt like.
        .order_by(Note.timestamp_s, Note.created_at, Note.id)
    )
    return list(rows)


async def create_note(
    session: AsyncSession,
    lesson_id: uuid.UUID,
    user: User,
    *,
    timestamp_s: int,
    content: str,
) -> Note:
    lesson = await _readable_lesson(session, lesson_id, user)

    note = Note(
        user_id=user.id,
        lesson_id=lesson.id,
        timestamp_s=timestamp_s,
        content=content,
    )
    session.add(note)
    await session.commit()
    await session.refresh(note)
    return note


async def update_note(
    session: AsyncSession,
    note_id: uuid.UUID,
    user: User,
    *,
    content: str,
    timestamp_s: int | None,
) -> Note:
    """Edit your own note. The lesson it belongs to cannot be changed.

    Moving a note to another lesson is not editing it, it is writing a
    different note -- and there is no interface that would ask for it.
    """
    note = await _own_note(session, note_id, user)

    note.content = content
    if timestamp_s is not None:
        note.timestamp_s = timestamp_s

    await session.commit()
    await session.refresh(note)
    return note


async def delete_note(session: AsyncSession, note_id: uuid.UUID, user: User) -> None:
    note = await _own_note(session, note_id, user)
    await session.delete(note)
    await session.commit()


# --- Bookmarks -------------------------------------------------------------


async def add_bookmark(
    session: AsyncSession, lesson_id: uuid.UUID, user: User
) -> None:
    """Flag a lesson. Doing it twice is doing it once.

    `ON CONFLICT DO NOTHING` rather than a lookup first: a bookmark is a fact,
    and two clicks racing each other should not turn one into an error.
    """
    lesson = await _readable_lesson(session, lesson_id, user)

    await session.execute(
        insert(Bookmark)
        .values(user_id=user.id, lesson_id=lesson.id)
        .on_conflict_do_nothing(constraint="uq_bookmarks_user_lesson")
    )
    await session.commit()


async def remove_bookmark(
    session: AsyncSession, lesson_id: uuid.UUID, user: User
) -> None:
    """Unflag it. Removing one that is not there is not an error either."""
    await session.execute(
        delete(Bookmark).where(
            Bookmark.user_id == user.id, Bookmark.lesson_id == lesson_id
        )
    )
    await session.commit()


async def bookmarked_lessons(
    session: AsyncSession, course_id: uuid.UUID, user: User
) -> list[uuid.UUID]:
    """Which lessons of one course this person has flagged.

    Answered for the whole course rather than lesson by lesson, because the
    table of contents draws every flag at once.
    """
    course = await courses_service.get_course_for_viewer(session, course_id, user)

    rows = await session.scalars(
        select(Bookmark.lesson_id)
        .join(Lesson, Lesson.id == Bookmark.lesson_id)
        .join(CourseSection, CourseSection.id == Lesson.section_id)
        .where(Bookmark.user_id == user.id, CourseSection.course_id == course.id)
    )
    return list(rows)
