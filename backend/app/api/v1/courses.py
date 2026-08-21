"""Course endpoints for instructors, plus the public detail page.

Authorization splits in two here, on purpose: *who may call this at all* is a
role check in the dependency, while *whose course is this* is an ownership
check in the service, which is the layer that has the row.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.core.deps import CurrentUser, DbSession, OptionalUser, require_role
from app.models import User
from app.schemas.courses import CourseCreate, CourseOut, CourseUpdate
from app.schemas.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, Page
from app.services import courses as courses_service

router = APIRouter(prefix="/courses", tags=["courses"])

Instructor = Annotated[User, Depends(require_role("instructor"))]


@router.post("", response_model=CourseOut, status_code=status.HTTP_201_CREATED)
async def create_course(
    payload: CourseCreate, instructor: Instructor, session: DbSession
) -> CourseOut:
    """Start a course. Instructors only; it opens as a draft owned by the caller."""
    course = await courses_service.create_course(session, instructor, payload)
    return CourseOut.model_validate(course)


@router.get("/me", response_model=Page[CourseOut])
async def list_my_courses(
    instructor: Instructor,
    session: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
) -> Page[CourseOut]:
    """The caller's own courses in every status, newest first.

    Declared before `/{course_id}` so that "me" is never parsed as an id.
    """
    items, total = await courses_service.list_own_courses(
        session, instructor, page=page, page_size=page_size
    )
    return Page[CourseOut](
        items=[CourseOut.model_validate(course) for course in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{course_id}", response_model=CourseOut)
async def get_course(
    course_id: uuid.UUID, viewer: OptionalUser, session: DbSession
) -> CourseOut:
    """One course. Public once published, private to its owner before that.

    Sign-in is optional rather than required: this is the page a search engine
    and a prospective student both land on.
    """
    course = await courses_service.get_course_for_viewer(session, course_id, viewer)
    return CourseOut.model_validate(course)


@router.patch("/{course_id}", response_model=CourseOut)
async def update_course(
    course_id: uuid.UUID,
    payload: CourseUpdate,
    current_user: CurrentUser,
    session: DbSession,
) -> CourseOut:
    """Edit your own course. Only the fields in `CourseUpdate` can move."""
    course = await courses_service.update_course(
        session, course_id, current_user, payload
    )
    return CourseOut.model_validate(course)


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course(
    course_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> None:
    """Take a course down. Soft delete -- students who bought it keep watching."""
    await courses_service.delete_course(session, course_id, current_user)


@router.post("/{course_id}/submit", response_model=CourseOut)
async def submit_course(
    course_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> CourseOut:
    """Send a draft for review. Auto-approved until Phase 5 builds the queue."""
    course = await courses_service.submit_for_review(session, course_id, current_user)
    return CourseOut.model_validate(course)


@router.post("/{course_id}/unpublish", response_model=CourseOut)
async def unpublish_course(
    course_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> CourseOut:
    """Pull a published course back to draft."""
    course = await courses_service.unpublish(session, course_id, current_user)
    return CourseOut.model_validate(course)
