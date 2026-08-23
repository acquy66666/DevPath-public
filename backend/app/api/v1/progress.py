"""Recording how far through a course somebody is.

Both routes belong to the caller: neither takes a user id, and both refuse
anyone without an enrolment in the course the lesson belongs to.
"""

import uuid

from fastapi import APIRouter

from app.core.deps import CurrentUser, DbSession
from app.schemas.progress import CourseProgressOut, LessonProgressOut, ProgressIn
from app.services import progress as progress_service

router = APIRouter(tags=["progress"])


@router.put("/lessons/{lesson_id}/progress", response_model=LessonProgressOut)
async def save_progress(
    lesson_id: uuid.UUID,
    payload: ProgressIn,
    current_user: CurrentUser,
    session: DbSession,
) -> LessonProgressOut:
    """Save the player's position, and optionally finish the lesson.

    PUT rather than POST: the same body sent twice leaves the same single row,
    which is exactly what a heartbeat every ten seconds needs to be true.

    403 `NOT_ENROLLED` for somebody watching a preview without signing up --
    there is no enrolment for the progress to belong to.
    """
    progress = await progress_service.save_position(
        session,
        lesson_id,
        current_user,
        last_position_s=payload.last_position_s,
        completed=payload.completed,
    )
    return LessonProgressOut.model_validate(progress)


@router.get("/courses/{course_id}/progress", response_model=CourseProgressOut)
async def get_course_progress(
    course_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> CourseProgressOut:
    """Your progress through one course, in a single call."""
    enrollment, rows, lesson_ids = await progress_service.course_progress(
        session, course_id, current_user
    )

    known = set(lesson_ids)
    return CourseProgressOut(
        enrollment_id=enrollment.id,
        completed_at=enrollment.completed_at,
        lesson_count=len(lesson_ids),
        # Counted against the course as it stands: a lesson that has since been
        # deleted should not keep counting towards a percentage.
        completed_count=sum(
            1
            for row in rows
            if row.completed_at is not None and row.lesson_id in known
        ),
        resume_lesson_id=progress_service.resume_lesson_id(rows, lesson_ids),
        lessons=[
            LessonProgressOut.model_validate(row) for row in rows if row.lesson_id in known
        ],
    )
