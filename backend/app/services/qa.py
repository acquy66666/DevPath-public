"""Questions and answers under a lesson.

**Who takes part** is the people taking the course and the people running it:
a learner enrolled in it, its instructor, or an admin (`courses.may_manage`).
Everyone else is 403 `NOT_ENROLLED` -- including on a preview lesson, which
anybody may *watch*: the questions under it are a conversation among the
course's learners, not part of the free sample.

**What each of them may do to a thread that is not theirs:**

* editing a question's title or body is its asker's alone;
* marking it resolved, and deleting a question or a reply, is its author's or
  the course staff's -- the instructor tidies their own course's board;
* voting is for anyone but the asker ("I have this question too" says nothing
  when the person saying it is the one who asked).

**A reply by the course's instructor carries a badge** (`is_instructor_reply`),
decided as the reply is written. An admin answering is staff, but not the
person who teaches the course, so their reply does not.

**Answering somebody's question notifies them**, and asking one notifies the
course's instructor, each in the same transaction as the write
(`services/notifications.py`). Nobody is notified about their own words.

Every count on a thread -- votes, replies, "the instructor has answered" -- is
worked out when the list is read, with no counter columns to keep in step. A
lesson's board is tens of rows, and the instructor's inbox is paged.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from fastapi import status
from sqlalchemy import ColumnElement, Select, delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DomainError
from app.models import (
    NOTIFICATION_QA_QUESTION,
    NOTIFICATION_QA_REPLY,
    Course,
    CourseSection,
    Lesson,
    QaReply,
    QaThread,
    QaVote,
    User,
)
from app.services import courses as courses_service
from app.services import enrollments as enrollments_service
from app.services import notifications as notifications_service
from app.services.courses import CourseNotFoundError
from app.services.curriculum import LessonNotFoundError

ThreadSort = Literal["newest", "top"]
THREAD_SORTS: tuple[ThreadSort, ...] = ("newest", "top")


class QaNotEnrolledError(DomainError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "NOT_ENROLLED"


class QaThreadNotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "QA_THREAD_NOT_FOUND"


class QaReplyNotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "QA_REPLY_NOT_FOUND"


class QaNotAllowedError(DomainError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "QA_NOT_ALLOWED"


class OwnThreadVoteError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    code = "CANNOT_VOTE_OWN_THREAD"


@dataclass(frozen=True, slots=True)
class Place:
    """Where a question lives, and whether the caller runs that course."""

    course: Course
    lesson: Lesson
    staff: bool


@dataclass(frozen=True, slots=True)
class ThreadView:
    """A question the way every screen shows it: with its numbers and its place."""

    thread: QaThread
    author: User
    lesson: Lesson
    course: Course
    vote_count: int
    reply_count: int
    has_instructor_reply: bool
    voted: bool


# --- Who is asking ---------------------------------------------------------


async def _admit(session: AsyncSession, course: Course, lesson: Lesson, user: User) -> Place:
    if courses_service.may_manage(course, user):
        return Place(course=course, lesson=lesson, staff=True)
    if await enrollments_service.find_for_course(session, course.id, user) is None:
        raise QaNotEnrolledError("Hỏi đáp dành cho học viên đã đăng ký khóa học")
    return Place(course=course, lesson=lesson, staff=False)


async def _place_of_lesson(session: AsyncSession, lesson_id: uuid.UUID, user: User) -> Place:
    row = (
        await session.execute(
            select(Lesson, CourseSection.course_id)
            .join(CourseSection, CourseSection.id == Lesson.section_id)
            .where(Lesson.id == lesson_id)
        )
    ).one_or_none()
    if row is None:
        raise LessonNotFoundError("Không tìm thấy bài học")

    lesson, course_id = row
    # A course that went back to draft is gone for its learners here exactly as
    # it is on the learning page: 404, from the rule that decides that.
    course = await courses_service.get_course_for_viewer(session, course_id, user)
    return await _admit(session, course, lesson, user)


async def _thread_and_place(
    session: AsyncSession, thread_id: uuid.UUID, user: User
) -> tuple[QaThread, Place]:
    thread = await session.get(QaThread, thread_id)
    if thread is None:
        raise QaThreadNotFoundError("Không tìm thấy câu hỏi")
    try:
        place = await _place_of_lesson(session, thread.lesson_id, user)
    except CourseNotFoundError:
        # The question exists, but not anywhere this reader can see.
        raise QaThreadNotFoundError("Không tìm thấy câu hỏi") from None
    return thread, place


# --- Reading threads -------------------------------------------------------


def _threads(viewer: User) -> Select:
    """Every thread with its numbers, from the point of view of one reader."""
    vote_count = (
        select(func.count())
        .select_from(QaVote)
        .where(QaVote.thread_id == QaThread.id)
        .correlate(QaThread)
        .scalar_subquery()
        .label("vote_count")
    )
    reply_count = (
        select(func.count())
        .select_from(QaReply)
        .where(QaReply.thread_id == QaThread.id)
        .correlate(QaThread)
        .scalar_subquery()
        .label("reply_count")
    )
    voted = (
        select(QaVote.id)
        .where(QaVote.thread_id == QaThread.id, QaVote.user_id == viewer.id)
        .correlate(QaThread)
        .exists()
        .label("voted")
    )
    return (
        select(
            QaThread,
            User,
            Lesson,
            Course,
            vote_count,
            reply_count,
            _instructor_answered().label("has_instructor_reply"),
            voted,
        )
        .join(User, User.id == QaThread.user_id)
        .join(Lesson, Lesson.id == QaThread.lesson_id)
        .join(CourseSection, CourseSection.id == Lesson.section_id)
        .join(Course, Course.id == CourseSection.course_id)
    )


def _instructor_answered() -> ColumnElement[bool]:
    return (
        select(QaReply.id)
        .where(QaReply.thread_id == QaThread.id, QaReply.is_instructor_reply)
        .correlate(QaThread)
        .exists()
    )


def _count(*conditions: ColumnElement[bool]) -> Select:
    """How many threads match -- over the same joins `_threads` reads through."""
    return (
        select(func.count())
        .select_from(QaThread)
        .join(Lesson, Lesson.id == QaThread.lesson_id)
        .join(CourseSection, CourseSection.id == Lesson.section_id)
        .join(Course, Course.id == CourseSection.course_id)
        .where(*conditions)
    )


def _view(row) -> ThreadView:
    thread, author, lesson, course, votes, replies, answered, voted = row
    return ThreadView(
        thread=thread,
        author=author,
        lesson=lesson,
        course=course,
        vote_count=votes,
        reply_count=replies,
        has_instructor_reply=answered,
        voted=voted,
    )


async def _one(session: AsyncSession, thread_id: uuid.UUID, user: User) -> ThreadView:
    # `populate_existing`: straight after a commit the thread is already in the
    # session with `updated_at` stale, and an async session cannot lazy-load it.
    row = (
        await session.execute(
            _threads(user).where(QaThread.id == thread_id).execution_options(populate_existing=True)
        )
    ).one()
    return _view(row)


async def list_threads(
    session: AsyncSession,
    lesson_id: uuid.UUID,
    user: User,
    *,
    sort: ThreadSort,
    page: int,
    page_size: int,
) -> tuple[list[ThreadView], int]:
    """One lesson's questions: newest first, or most-asked first.

    Ties in the vote count go to the newer question, and ties in time to the
    id, so a page boundary never shows the same thread twice.
    """
    place = await _place_of_lesson(session, lesson_id, user)
    where = QaThread.lesson_id == place.lesson.id

    stmt = _threads(user).where(where)
    newest = (QaThread.created_at.desc(), QaThread.id.desc())
    if sort == "top":
        stmt = stmt.order_by(stmt.selected_columns.vote_count.desc(), *newest)
    else:
        stmt = stmt.order_by(*newest)

    rows = await session.execute(stmt.limit(page_size).offset((page - 1) * page_size))
    total = await session.scalar(_count(where))
    return [_view(row) for row in rows], total or 0


async def get_thread(session: AsyncSession, thread_id: uuid.UUID, user: User) -> ThreadView:
    thread, _ = await _thread_and_place(session, thread_id, user)
    return await _one(session, thread.id, user)


async def visible_thread(session: AsyncSession, thread_id: uuid.UUID, user: User) -> QaThread:
    """The thread, if this person may read it -- the same rule as every Q&A read.

    For reporting (`services/reports.py`): you can only flag what you can see.
    """
    thread, _ = await _thread_and_place(session, thread_id, user)
    return thread


async def list_for_instructor(
    session: AsyncSession,
    instructor: User,
    *,
    course_id: uuid.UUID | None,
    unanswered: bool,
    page: int,
    page_size: int,
) -> tuple[list[ThreadView], int]:
    """Questions across the caller's own courses, newest first.

    `unanswered` means what the instructor is looking for when they open the
    page: no reply from them yet, and the asker has not said it is solved.
    """
    conditions: list[ColumnElement[bool]] = [
        Course.instructor_id == instructor.id,
        Course.deleted_at.is_(None),
    ]
    if course_id is not None:
        conditions.append(Course.id == course_id)
    if unanswered:
        conditions.append(~_instructor_answered())
        conditions.append(QaThread.resolved_at.is_(None))

    rows = await session.execute(
        _threads(instructor)
        .where(*conditions)
        .order_by(QaThread.created_at.desc(), QaThread.id.desc())
        .limit(page_size)
        .offset((page - 1) * page_size)
    )
    total = await session.scalar(_count(*conditions))
    return [_view(row) for row in rows], total or 0


# --- Writing threads -------------------------------------------------------


async def create_thread(
    session: AsyncSession, lesson_id: uuid.UUID, user: User, *, title: str, body: str
) -> ThreadView:
    place = await _place_of_lesson(session, lesson_id, user)

    thread = QaThread(lesson_id=place.lesson.id, user_id=user.id, title=title, body=body)
    session.add(thread)
    await session.flush()

    # The instructor hears about a question the way the asker hears about its
    # answer. Not when they asked it themselves.
    if user.id != place.course.instructor_id:
        notifications_service.add(
            session,
            user_id=place.course.instructor_id,
            type=NOTIFICATION_QA_QUESTION,
            payload={
                "thread_id": str(thread.id),
                "lesson_id": str(place.lesson.id),
                "course_id": str(place.course.id),
                "course_title": place.course.title,
                "lesson_title": place.lesson.title,
                "thread_title": thread.title,
                "asker_name": user.full_name,
            },
        )

    await session.commit()
    return await _one(session, thread.id, user)


async def update_thread(
    session: AsyncSession,
    thread_id: uuid.UUID,
    user: User,
    *,
    title: str | None = None,
    body: str | None = None,
    resolved: bool | None = None,
) -> ThreadView:
    """Change a question, or say whether it has been answered.

    `None` leaves a field as it is. Every change is checked before any is
    applied, so a request that may do one half of what it asks does neither.
    """
    thread, place = await _thread_and_place(session, thread_id, user)
    is_author = thread.user_id == user.id

    if (title is not None or body is not None) and not is_author:
        raise QaNotAllowedError("Chỉ người đặt câu hỏi mới sửa được câu hỏi")
    if resolved is not None and not (is_author or place.staff):
        raise QaNotAllowedError(
            "Chỉ người đặt câu hỏi hoặc giảng viên mới đánh dấu được câu hỏi đã giải quyết"
        )

    if title is not None:
        thread.title = title
    if body is not None:
        thread.body = body
    if resolved is True and thread.resolved_at is None:
        # Keeps the first time it was marked: saying "solved" twice is once.
        thread.resolved_at = datetime.now(UTC)
    elif resolved is False:
        thread.resolved_at = None

    await session.commit()
    return await _one(session, thread.id, user)


async def delete_thread(session: AsyncSession, thread_id: uuid.UUID, user: User) -> None:
    """The asker or the course staff. Its replies and votes go with it."""
    thread, place = await _thread_and_place(session, thread_id, user)
    if thread.user_id != user.id and not place.staff:
        raise QaNotAllowedError("Bạn không thể xóa câu hỏi của người khác")

    await session.delete(thread)
    await session.commit()


# --- Replies ---------------------------------------------------------------


async def list_replies(
    session: AsyncSession, thread_id: uuid.UUID, user: User, *, page: int, page_size: int
) -> tuple[list[tuple[QaReply, User]], int]:
    """A thread's answers in the order they were written -- a conversation."""
    thread, _ = await _thread_and_place(session, thread_id, user)

    rows = await session.execute(
        select(QaReply, User)
        .join(User, User.id == QaReply.user_id)
        .where(QaReply.thread_id == thread.id)
        .order_by(QaReply.created_at, QaReply.id)
        .limit(page_size)
        .offset((page - 1) * page_size)
    )
    total = await session.scalar(
        select(func.count()).select_from(QaReply).where(QaReply.thread_id == thread.id)
    )
    return [(reply, author) for reply, author in rows], total or 0


async def create_reply(
    session: AsyncSession, thread_id: uuid.UUID, user: User, *, body: str
) -> QaReply:
    thread, place = await _thread_and_place(session, thread_id, user)

    reply = QaReply(
        thread_id=thread.id,
        user_id=user.id,
        body=body,
        is_instructor_reply=user.id == place.course.instructor_id,
    )
    session.add(reply)
    await session.flush()

    if thread.user_id != user.id:
        notifications_service.add(
            session,
            user_id=thread.user_id,
            type=NOTIFICATION_QA_REPLY,
            payload={
                "thread_id": str(thread.id),
                "reply_id": str(reply.id),
                "lesson_id": str(place.lesson.id),
                "course_id": str(place.course.id),
                "course_slug": place.course.slug,
                "thread_title": thread.title,
                "replier_name": user.full_name,
                "is_instructor_reply": reply.is_instructor_reply,
            },
        )

    await session.commit()
    await session.refresh(reply)
    return reply


async def delete_reply(session: AsyncSession, reply_id: uuid.UUID, user: User) -> None:
    """The person who wrote it, or the course staff.

    The notification it sent stays: it records that somebody answered, and the
    reader following it finds the thread as it now is.
    """
    reply = await session.get(QaReply, reply_id)
    if reply is None:
        raise QaReplyNotFoundError("Không tìm thấy câu trả lời")

    _, place = await _thread_and_place(session, reply.thread_id, user)
    if reply.user_id != user.id and not place.staff:
        raise QaNotAllowedError("Bạn không thể xóa câu trả lời của người khác")

    await session.delete(reply)
    await session.commit()


# --- Votes -----------------------------------------------------------------


async def vote(session: AsyncSession, thread_id: uuid.UUID, user: User) -> None:
    """ "I have this question too." Twice is once, as with a bookmark."""
    thread, _ = await _thread_and_place(session, thread_id, user)
    if thread.user_id == user.id:
        raise OwnThreadVoteError("Bạn không thể bình chọn câu hỏi của chính mình")

    await session.execute(
        insert(QaVote)
        .values(thread_id=thread.id, user_id=user.id)
        .on_conflict_do_nothing(constraint="uq_qa_votes_thread_user")
    )
    await session.commit()


async def unvote(session: AsyncSession, thread_id: uuid.UUID, user: User) -> None:
    """Take it back. Taking back a vote you never gave is not an error either."""
    thread, _ = await _thread_and_place(session, thread_id, user)

    await session.execute(
        delete(QaVote).where(QaVote.thread_id == thread.id, QaVote.user_id == user.id)
    )
    await session.commit()
