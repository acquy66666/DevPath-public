"""Where a student has got to, lesson by lesson.

Written far more often than it is read: the player sends a position every few
seconds. So the write path is one upsert and nothing else -- no history, no
extra rows, and the same statement whether this is the first heartbeat of a
lesson or the thousandth.

Progress belongs to an enrolment, not to an account. An instructor previewing
their own lesson has no enrolment and therefore no progress, which is right:
they are not studying the course, and their watching should not appear in
anybody's completion figures.
"""

import uuid
from datetime import UTC, datetime

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DomainError
from app.models import CourseSection, Enrollment, Lesson, LessonProgress, User
from app.services import after_commit, certificates, gamification
from app.services import courses as courses_service
from app.services import enrollments as enrollments_service


class NotEnrolledError(DomainError):
    """Reading a preview needs nothing; recording progress needs an enrolment."""

    status_code = status.HTTP_403_FORBIDDEN
    code = "NOT_ENROLLED"


async def enrollment_for_course(
    session: AsyncSession, course_id: uuid.UUID, user: User
) -> Enrollment:
    """The caller's enrolment in a course, or 403."""
    enrollment = await enrollments_service.find_for_course(session, course_id, user)
    if enrollment is None:
        raise NotEnrolledError("Bạn cần đăng ký khóa học này trước")
    return enrollment


async def _course_id_of_lesson(session: AsyncSession, lesson: Lesson) -> uuid.UUID:
    section = await session.get(CourseSection, lesson.section_id)
    if section is None:
        # The foreign key is NOT NULL with ON DELETE CASCADE, so a lesson
        # without its section does not exist.
        raise courses_service.CourseNotFoundError("Không tìm thấy khóa học")
    return section.course_id


async def _lesson_ids_of_course(
    session: AsyncSession, course_id: uuid.UUID
) -> list[uuid.UUID]:
    """Every lesson of a course, in the order a student walks them."""
    rows = await session.scalars(
        select(Lesson.id)
        .join(CourseSection, CourseSection.id == Lesson.section_id)
        .where(CourseSection.course_id == course_id)
        .order_by(CourseSection.position, Lesson.position)
    )
    return list(rows)


async def _refresh_course_completion(
    session: AsyncSession, enrollment: Enrollment, course_id: uuid.UUID
) -> None:
    """Set or clear `enrollments.completed_at` from the lessons underneath it.

    The enrolment has no status column: finishing a course is not a thing
    anybody declares, it is what "every lesson is done" adds up to. Computing
    it here means the two can never drift apart -- and un-completing a lesson
    takes the course's completion back with it.
    """
    lesson_ids = await _lesson_ids_of_course(session, course_id)

    done = await session.scalar(
        select(func.count())
        .select_from(LessonProgress)
        .where(
            LessonProgress.enrollment_id == enrollment.id,
            LessonProgress.lesson_id.in_(lesson_ids),
            LessonProgress.completed_at.is_not(None),
        )
    ) or 0

    # A course with no lessons is not a finished course, it is an empty one.
    finished = len(lesson_ids) > 0 and done == len(lesson_ids)

    if finished and enrollment.completed_at is None:
        enrollment.completed_at = datetime.now(UTC)
        # The one place a course becomes finished, whatever finished it -- so
        # the one place a certificate is issued. Once per enrolment: finishing
        # again after unticking a lesson finds it already there.
        await certificates.issue(session, enrollment, issued_at=enrollment.completed_at)
    elif not finished and enrollment.completed_at is not None:
        # The certificate stays. It was true on the day it was issued.
        enrollment.completed_at = None


async def save_position(
    session: AsyncSession,
    lesson_id: uuid.UUID,
    user: User,
    *,
    last_position_s: int,
    completed: bool | None,
) -> LessonProgress:
    """Record where the player is, and optionally that the lesson is finished.

    `completed` is three-valued on purpose. The heartbeat leaves it out, and a
    heartbeat must never be able to un-finish a lesson somebody has already
    completed -- which is exactly what a plain boolean defaulting to False
    would do every ten seconds.
    """
    lesson = await session.get(Lesson, lesson_id)
    if lesson is None:
        raise courses_service.CourseNotFoundError("Không tìm thấy bài học")

    course_id = await _course_id_of_lesson(session, lesson)
    enrollment = await enrollment_for_course(session, course_id, user)

    values: dict = {
        "enrollment_id": enrollment.id,
        "lesson_id": lesson.id,
        "last_position_s": last_position_s,
    }
    updates: dict = {
        "last_position_s": last_position_s,
        "updated_at": func.now(),
    }

    if completed is True:
        values["completed_at"] = func.now()
        # Keep the first completion time: finishing something twice does not
        # move the day you finished it.
        updates["completed_at"] = func.coalesce(LessonProgress.completed_at, func.now())
    elif completed is False:
        values["completed_at"] = None
        updates["completed_at"] = None

    statement = (
        insert(LessonProgress)
        .values(**values)
        .on_conflict_do_update(
            constraint="uq_lesson_progress_enrollment_lesson", set_=updates
        )
        .returning(LessonProgress.id)
    )
    progress_id = await session.scalar(statement)

    if completed is not None:
        await _refresh_course_completion(session, enrollment, course_id)

    if completed is True:
        # Only the tick: a heartbeat is watching, not finishing, and a video
        # playing in a background tab must not keep a streak alive.
        await gamification.award(
            session, user_id=user.id, reason="lesson_completed", ref_id=lesson.id
        )
        await gamification.record_active_day(
            session, user_id=user.id, day=gamification.today_in_vietnam()
        )

    await session.commit()
    await after_commit.run(session)

    progress = await session.get(LessonProgress, progress_id)
    if progress is None:
        # The row was just written in this transaction.
        raise courses_service.CourseNotFoundError("Không tìm thấy tiến độ")
    return progress


async def course_progress(
    session: AsyncSession, course_id: uuid.UUID, user: User
) -> tuple[Enrollment, list[LessonProgress], list[uuid.UUID]]:
    """Everything the learning page needs: the enrolment, the rows, the order.

    One call rather than one per lesson: the page draws a table of contents
    with a tick against each finished lesson, and twenty round trips to fill it
    in would be twenty round trips.
    """
    # Reached through the course, so an unpublished one is 404 before the
    # enrolment check can say anything about it.
    course = await courses_service.get_course_for_viewer(session, course_id, user)
    enrollment = await enrollment_for_course(session, course.id, user)

    lesson_ids = await _lesson_ids_of_course(session, course.id)
    rows = await session.scalars(
        select(LessonProgress).where(LessonProgress.enrollment_id == enrollment.id)
    )
    return enrollment, list(rows), lesson_ids


def resume_lesson_id(
    progress: list[LessonProgress], lesson_ids: list[uuid.UUID]
) -> uuid.UUID | None:
    """Where "tiếp tục học" should go.

    The lesson touched most recently -- which is where the reader actually
    stopped, whether or not they finished it. With nothing watched yet, the
    course starts at its first lesson.
    """
    known = set(lesson_ids)
    watched = [row for row in progress if row.lesson_id in known]

    if watched:
        return max(watched, key=lambda row: row.updated_at).lesson_id
    return lesson_ids[0] if lesson_ids else None



async def mark_lesson_solved(
    session: AsyncSession, *, lesson_id: uuid.UUID, user_id: uuid.UUID
) -> bool:
    """Finish a lesson because its exercise was solved.

    The counterpart of `save_position` for lessons nobody watches. A video is
    finished when the student says so; a code exercise is finished when every
    test case passes, and asking them to also tick a box is asking them to
    tell the system something it just watched happen.

    Written by the grading worker, so it takes ids rather than a `User`: there
    is no request and no caller to authorise. That is safe here because the
    only thing it can do is record a completion for a submission that has
    already been graded -- and it does nothing at all for somebody with no
    enrolment, which is how an instructor trying their own exercise stays out
    of their course's completion figures.

    Pays the lesson's XP too, the first time. What finished it (a quiz, an
    exercise) is the caller's to pay for, and only when this returns True.

    Does not commit: the caller is mid-transaction and owns that decision.
    Returns whether an enrolment was found to record against.
    """
    lesson = await session.get(Lesson, lesson_id)
    if lesson is None:
        return False

    course_id = await _course_id_of_lesson(session, lesson)
    enrollment = await session.scalar(
        select(Enrollment).where(
            Enrollment.user_id == user_id, Enrollment.course_id == course_id
        )
    )
    if enrollment is None:
        return False

    await session.execute(
        insert(LessonProgress)
        .values(
            enrollment_id=enrollment.id,
            lesson_id=lesson.id,
            last_position_s=0,
            completed_at=func.now(),
        )
        .on_conflict_do_update(
            constraint="uq_lesson_progress_enrollment_lesson",
            # Only the completion: a lesson that already has a position keeps
            # it, and one solved twice keeps the day it was first solved.
            set_={
                "completed_at": func.coalesce(LessonProgress.completed_at, func.now()),
                "updated_at": func.now(),
            },
        )
    )
    await _refresh_course_completion(session, enrollment, course_id)
    await gamification.award(
        session, user_id=user_id, reason="lesson_completed", ref_id=lesson.id
    )
    return True
