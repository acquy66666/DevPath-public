"""Notes and bookmarks. Every route here answers only about the caller."""

import uuid

from fastapi import APIRouter, status

from app.core.deps import CurrentUser, DbSession
from app.schemas.study import BookmarkedLessonsOut, NoteCreate, NoteOut, NoteUpdate
from app.services import study as study_service

router = APIRouter(tags=["study"])


@router.get("/lessons/{lesson_id}/notes", response_model=list[NoteOut])
async def list_notes(
    lesson_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> list[NoteOut]:
    """Your notes on one lesson, in the order they happen in the video.

    Not paginated: these are one person's notes on one lesson, and a list that
    ever needs a second page is not a list of notes any more.
    """
    notes = await study_service.list_notes(session, lesson_id, current_user)
    return [NoteOut.model_validate(note) for note in notes]


@router.post(
    "/lessons/{lesson_id}/notes",
    response_model=NoteOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_note(
    lesson_id: uuid.UUID,
    payload: NoteCreate,
    current_user: CurrentUser,
    session: DbSession,
) -> NoteOut:
    """Write a note on a lesson you can open.

    403 `LESSON_LOCKED` on a lesson you cannot -- the same answer reading it
    would give, because this is the same permission.
    """
    note = await study_service.create_note(
        session,
        lesson_id,
        current_user,
        timestamp_s=payload.timestamp_s,
        content=payload.content,
    )
    return NoteOut.model_validate(note)


@router.patch("/notes/{note_id}", response_model=NoteOut)
async def update_note(
    note_id: uuid.UUID,
    payload: NoteUpdate,
    current_user: CurrentUser,
    session: DbSession,
) -> NoteOut:
    """Edit your own note. Somebody else's answers 404, not 403."""
    note = await study_service.update_note(
        session,
        note_id,
        current_user,
        content=payload.content,
        timestamp_s=payload.timestamp_s,
    )
    return NoteOut.model_validate(note)


@router.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    note_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> None:
    await study_service.delete_note(session, note_id, current_user)


@router.put(
    "/lessons/{lesson_id}/bookmark", status_code=status.HTTP_204_NO_CONTENT
)
async def add_bookmark(
    lesson_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> None:
    """Flag a lesson to come back to. PUT because doing it twice changes nothing."""
    await study_service.add_bookmark(session, lesson_id, current_user)


@router.delete(
    "/lessons/{lesson_id}/bookmark", status_code=status.HTTP_204_NO_CONTENT
)
async def remove_bookmark(
    lesson_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> None:
    """Remove the flag. Removing one that was never there is not an error."""
    await study_service.remove_bookmark(session, lesson_id, current_user)


@router.get("/courses/{course_id}/bookmarks", response_model=BookmarkedLessonsOut)
async def list_bookmarks(
    course_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> BookmarkedLessonsOut:
    """Which lessons of this course you have flagged, for the table of contents."""
    lesson_ids = await study_service.bookmarked_lessons(
        session, course_id, current_user
    )
    return BookmarkedLessonsOut(lesson_ids=lesson_ids)
