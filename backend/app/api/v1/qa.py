"""Q&A under a lesson.

Everything here needs a signed-in caller who takes part in the course -- an
enrolled learner, its instructor, or an admin. Who may do what to whose thread
is decided in `services/qa.py`, because it needs the thread and the course.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.core.deps import CurrentUser, DbSession, require_role
from app.models import QaReply, User
from app.schemas.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, Page
from app.schemas.qa import (
    QaAuthorOut,
    QaCourseRef,
    QaLessonRef,
    QaReplyCreate,
    QaReplyOut,
    QaThreadCreate,
    QaThreadOut,
    QaThreadUpdate,
)
from app.services import qa as qa_service
from app.services.qa import ThreadSort, ThreadView

router = APIRouter(tags=["qa"])

Instructor = Annotated[User, Depends(require_role("instructor"))]
PageNumber = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)]


def _thread_out(view: ThreadView) -> QaThreadOut:
    thread = view.thread
    return QaThreadOut(
        id=thread.id,
        title=thread.title,
        body=thread.body,
        author=QaAuthorOut.model_validate(view.author),
        lesson=QaLessonRef.model_validate(view.lesson),
        course=QaCourseRef.model_validate(view.course),
        vote_count=view.vote_count,
        voted=view.voted,
        reply_count=view.reply_count,
        has_instructor_reply=view.has_instructor_reply,
        resolved_at=thread.resolved_at,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
    )


def _reply_out(reply: QaReply, author: User) -> QaReplyOut:
    return QaReplyOut(
        id=reply.id,
        thread_id=reply.thread_id,
        body=reply.body,
        author=QaAuthorOut.model_validate(author),
        is_instructor_reply=reply.is_instructor_reply,
        created_at=reply.created_at,
        updated_at=reply.updated_at,
    )


# --- Threads ---------------------------------------------------------------


@router.get("/lessons/{lesson_id}/qa-threads", response_model=Page[QaThreadOut])
async def list_lesson_threads(
    lesson_id: uuid.UUID,
    current_user: CurrentUser,
    session: DbSession,
    sort: ThreadSort = "newest",
    page: PageNumber = 1,
    page_size: PageSize = DEFAULT_PAGE_SIZE,
) -> Page[QaThreadOut]:
    """This lesson's questions. `sort=top` puts the most-asked first.

    403 `NOT_ENROLLED` for anyone not taking the course -- on a preview lesson
    too.
    """
    views, total = await qa_service.list_threads(
        session, lesson_id, current_user, sort=sort, page=page, page_size=page_size
    )
    return Page[QaThreadOut](
        items=[_thread_out(view) for view in views],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/lessons/{lesson_id}/qa-threads",
    response_model=QaThreadOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_thread(
    lesson_id: uuid.UUID,
    payload: QaThreadCreate,
    current_user: CurrentUser,
    session: DbSession,
) -> QaThreadOut:
    """Ask a question about this lesson."""
    view = await qa_service.create_thread(
        session, lesson_id, current_user, title=payload.title, body=payload.body
    )
    return _thread_out(view)


@router.get("/qa-threads/{thread_id}", response_model=QaThreadOut)
async def get_thread(
    thread_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> QaThreadOut:
    view = await qa_service.get_thread(session, thread_id, current_user)
    return _thread_out(view)


@router.patch("/qa-threads/{thread_id}", response_model=QaThreadOut)
async def update_thread(
    thread_id: uuid.UUID,
    payload: QaThreadUpdate,
    current_user: CurrentUser,
    session: DbSession,
) -> QaThreadOut:
    """Edit your question, or mark it resolved (`{"resolved": true}`).

    Title and body are the asker's alone; `resolved` is the asker's or the
    course staff's. 403 `QA_NOT_ALLOWED` otherwise.
    """
    view = await qa_service.update_thread(
        session,
        thread_id,
        current_user,
        title=payload.title,
        body=payload.body,
        resolved=payload.resolved,
    )
    return _thread_out(view)


@router.delete("/qa-threads/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_thread(
    thread_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> None:
    """The asker, or the course's instructor tidying their board."""
    await qa_service.delete_thread(session, thread_id, current_user)


# --- Votes -----------------------------------------------------------------


@router.put("/qa-threads/{thread_id}/vote", status_code=status.HTTP_204_NO_CONTENT)
async def vote_thread(thread_id: uuid.UUID, current_user: CurrentUser, session: DbSession) -> None:
    """ "I have this question too." PUT: voting twice is voting once.

    409 `CANNOT_VOTE_OWN_THREAD` on your own question.
    """
    await qa_service.vote(session, thread_id, current_user)


@router.delete("/qa-threads/{thread_id}/vote", status_code=status.HTTP_204_NO_CONTENT)
async def unvote_thread(
    thread_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> None:
    await qa_service.unvote(session, thread_id, current_user)


# --- Replies ---------------------------------------------------------------


@router.get("/qa-threads/{thread_id}/replies", response_model=Page[QaReplyOut])
async def list_replies(
    thread_id: uuid.UUID,
    current_user: CurrentUser,
    session: DbSession,
    page: PageNumber = 1,
    page_size: PageSize = DEFAULT_PAGE_SIZE,
) -> Page[QaReplyOut]:
    """A thread's answers, oldest first."""
    rows, total = await qa_service.list_replies(
        session, thread_id, current_user, page=page, page_size=page_size
    )
    return Page[QaReplyOut](
        items=[_reply_out(reply, author) for reply, author in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/qa-threads/{thread_id}/replies",
    response_model=QaReplyOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_reply(
    thread_id: uuid.UUID,
    payload: QaReplyCreate,
    current_user: CurrentUser,
    session: DbSession,
) -> QaReplyOut:
    """Answer a question. The asker is notified, unless they are answering it."""
    reply = await qa_service.create_reply(session, thread_id, current_user, body=payload.body)
    return _reply_out(reply, current_user)


@router.delete("/qa-replies/{reply_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reply(reply_id: uuid.UUID, current_user: CurrentUser, session: DbSession) -> None:
    await qa_service.delete_reply(session, reply_id, current_user)


# --- The instructor's inbox ------------------------------------------------


@router.get("/instructor/qa-threads", response_model=Page[QaThreadOut])
async def list_instructor_threads(
    instructor: Instructor,
    session: DbSession,
    course_id: uuid.UUID | None = None,
    unanswered: bool = False,
    page: PageNumber = 1,
    page_size: PageSize = DEFAULT_PAGE_SIZE,
) -> Page[QaThreadOut]:
    """Questions asked in the caller's courses, newest first.

    The instructor cannot enrol in their own course, so the learning page is
    not where they read its questions -- this is. `unanswered=true` keeps the
    ones with no instructor reply that are not resolved yet.
    """
    views, total = await qa_service.list_for_instructor(
        session,
        instructor,
        course_id=course_id,
        unanswered=unanswered,
        page=page,
        page_size=page_size,
    )
    return Page[QaThreadOut](
        items=[_thread_out(view) for view in views],
        total=total,
        page=page,
        page_size=page_size,
    )
