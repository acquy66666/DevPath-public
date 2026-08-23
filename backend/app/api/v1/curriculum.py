"""Curriculum endpoints: sections, lessons, and their order.

Collections hang off their parent (`/courses/{id}/sections`), individual rows
do not (`/sections/{id}`, `/lessons/{id}`). Nesting the whole path would give
`/courses/{cid}/sections/{sid}/lessons/{lid}`, where the first two ids are
already implied by the third and the server would have to check they agree.
"""

import uuid

from fastapi import APIRouter, status

from app.core.deps import CurrentUser, DbSession, OptionalUser
from app.models import Lesson
from app.schemas.curriculum import (
    CurriculumOut,
    LessonCreate,
    LessonOrder,
    LessonOut,
    LessonSummary,
    LessonUpdate,
    SectionCreate,
    SectionOrder,
    SectionOut,
    SectionUpdate,
    SectionWithLessons,
)
from app.services import curriculum as curriculum_service
from app.services import video as video_service

router = APIRouter(tags=["curriculum"])


def lesson_out(lesson: Lesson) -> LessonOut:
    """One lesson, with its video attached when it has one.

    Built here rather than by `model_validate` alone: the playback URL is
    derived from configuration, not stored on the row.
    """
    out = LessonOut.model_validate(lesson)
    if lesson.video_asset is not None:
        out.video = video_service.video_out(lesson.video_asset)
    return out


# --- Reading ---------------------------------------------------------------


@router.get("/courses/{course_id}/curriculum", response_model=CurriculumOut)
async def get_curriculum(
    course_id: uuid.UUID, viewer: OptionalUser, session: DbSession
) -> CurriculumOut:
    """The table of contents. Public once the course is published.

    Lesson content is not in here: this is the list that convinces someone to
    enrol, and `GET /lessons/{id}` is what opens a lesson.
    """
    sections = await curriculum_service.get_curriculum(session, course_id, viewer)
    return CurriculumOut(
        sections=[
            SectionWithLessons(
                **SectionOut.model_validate(section).model_dump(),
                lessons=[LessonSummary.model_validate(lesson) for lesson in lessons],
            )
            for section, lessons in sections
        ]
    )


@router.get("/lessons/{lesson_id}", response_model=LessonOut)
async def get_lesson(
    lesson_id: uuid.UUID, viewer: OptionalUser, session: DbSession
) -> LessonOut:
    """One lesson in full: the owner's to edit, or a preview for everyone."""
    lesson = await curriculum_service.get_lesson_for_viewer(session, lesson_id, viewer)
    return lesson_out(lesson)


# --- Sections --------------------------------------------------------------


@router.post(
    "/courses/{course_id}/sections",
    response_model=SectionOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_section(
    course_id: uuid.UUID,
    payload: SectionCreate,
    current_user: CurrentUser,
    session: DbSession,
) -> SectionOut:
    """Add a section to the end of your own course."""
    section = await curriculum_service.create_section(
        session, course_id, current_user, payload.title
    )
    return SectionOut.model_validate(section)


@router.patch("/sections/{section_id}", response_model=SectionOut)
async def update_section(
    section_id: uuid.UUID,
    payload: SectionUpdate,
    current_user: CurrentUser,
    session: DbSession,
) -> SectionOut:
    section = await curriculum_service.update_section(
        session, section_id, current_user, payload.title
    )
    return SectionOut.model_validate(section)


@router.delete("/sections/{section_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_section(
    section_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> None:
    """Delete a section and everything in it. Hard delete -- nobody bought a section."""
    await curriculum_service.delete_section(session, section_id, current_user)


@router.put("/courses/{course_id}/sections/order", response_model=list[SectionOut])
async def reorder_sections(
    course_id: uuid.UUID,
    payload: SectionOrder,
    current_user: CurrentUser,
    session: DbSession,
) -> list[SectionOut]:
    """Set the order of every section at once, as it looks after a drag."""
    sections = await curriculum_service.reorder_sections(
        session, course_id, current_user, payload.section_ids
    )
    return [SectionOut.model_validate(section) for section in sections]


# --- Lessons ---------------------------------------------------------------


@router.post(
    "/sections/{section_id}/lessons",
    response_model=LessonOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_lesson(
    section_id: uuid.UUID,
    payload: LessonCreate,
    current_user: CurrentUser,
    session: DbSession,
) -> LessonOut:
    lesson = await curriculum_service.create_lesson(
        session, section_id, current_user, payload
    )
    return lesson_out(lesson)


@router.patch("/lessons/{lesson_id}", response_model=LessonOut)
async def update_lesson(
    lesson_id: uuid.UUID,
    payload: LessonUpdate,
    current_user: CurrentUser,
    session: DbSession,
) -> LessonOut:
    lesson = await curriculum_service.update_lesson(
        session, lesson_id, current_user, payload
    )
    return lesson_out(lesson)


@router.delete("/lessons/{lesson_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lesson(
    lesson_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> None:
    await curriculum_service.delete_lesson(session, lesson_id, current_user)


@router.put("/sections/{section_id}/lessons/order", response_model=list[LessonSummary])
async def reorder_lessons(
    section_id: uuid.UUID,
    payload: LessonOrder,
    current_user: CurrentUser,
    session: DbSession,
) -> list[LessonSummary]:
    """Set the complete contents of a section, in order.

    A lesson listed here that belongs to another section of the same course is
    moved in, and the section it left is renumbered.
    """
    lessons = await curriculum_service.reorder_lessons(
        session, section_id, current_user, payload.lesson_ids
    )
    return [LessonSummary.model_validate(lesson) for lesson in lessons]
