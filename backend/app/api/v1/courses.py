"""Course endpoints for instructors, plus the public detail page.

Authorization splits in two here, on purpose: *who may call this at all* is a
role check in the dependency, while *whose course is this* is an ownership
check in the service, which is the layer that has the row.
"""

import uuid
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.core.deps import CurrentUser, DbSession, OptionalUser, require_role
from app.models import User
from app.schemas.categories import CategoryOut
from app.schemas.courses import (
    CourseCardBase,
    CourseCardOut,
    CourseCreate,
    CourseDetailOut,
    CourseInstructorOut,
    CourseOut,
    CourseUpdate,
)
from app.schemas.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, Page
from app.services import catalog as catalog_service
from app.services import courses as courses_service
from app.services.tasks import TaskQueue, get_task_queue

router = APIRouter(prefix="/courses", tags=["courses"])

#: Celery, and overridden in tests.
Queue = Annotated[TaskQueue, Depends(get_task_queue)]

Instructor = Annotated[User, Depends(require_role("instructor"))]


@router.post("", response_model=CourseOut, status_code=status.HTTP_201_CREATED)
async def create_course(
    payload: CourseCreate, instructor: Instructor, session: DbSession
) -> CourseOut:
    """Start a course. Instructors only; it opens as a draft owned by the caller."""
    course = await courses_service.create_course(session, instructor, payload)
    return CourseOut.model_validate(course)


@router.get("", response_model=Page[CourseCardOut])
async def list_courses(
    session: DbSession,
    q: Annotated[
        str | None,
        Query(max_length=catalog_service.MAX_QUERY_LENGTH, description="Từ khóa tìm kiếm"),
    ] = None,
    category_id: uuid.UUID | None = None,
    price_min: Annotated[Decimal | None, Query(ge=0)] = None,
    price_max: Annotated[Decimal | None, Query(ge=0)] = None,
    rating_min: Annotated[Decimal | None, Query(ge=0, le=5)] = None,
    sort: catalog_service.Sort | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
) -> Page[CourseCardOut]:
    """The public catalogue. No sign-in: this is the page people browse first.

    Only published courses appear, whoever is asking -- an instructor's own
    drafts live on their dashboard, not in a listing anyone can page through.

    `sort` defaults to relevance when `q` is given and to newest otherwise;
    sorting a search by date would bury the best match on page four.
    """
    rows, total = await catalog_service.list_published(
        session,
        q=q,
        category_id=category_id,
        price_min=price_min,
        price_max=price_max,
        rating_min=rating_min,
        sort=sort,
        page=page,
        page_size=page_size,
    )

    return Page[CourseCardOut](
        items=[
            CourseCardOut(
                **CourseCardBase.model_validate(course).model_dump(),
                instructor=CourseInstructorOut.model_validate(instructor),
                category=CategoryOut.model_validate(category),
            )
            for course, instructor, category in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


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


@router.get("/by-slug/{slug}", response_model=CourseDetailOut)
async def get_course_by_slug(
    slug: str, viewer: OptionalUser, session: DbSession
) -> CourseDetailOut:
    """The public course page, addressed the way its URL spells it.

    Two segments, so this never collides with `/{course_id}`. Sign-in is
    optional: a search engine, a visitor and the owner previewing a draft all
    arrive at the same address, and the service decides what each may see.
    """
    detail = await courses_service.get_course_detail(session, slug, viewer)
    return CourseDetailOut(
        **CourseOut.model_validate(detail.course).model_dump(),
        instructor=CourseInstructorOut.model_validate(detail.instructor),
        category=CategoryOut.model_validate(detail.category),
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
    course_id: uuid.UUID,
    current_user: CurrentUser,
    session: DbSession,
    queue: Queue,
) -> CourseOut:
    """Send a draft for review. Auto-approved until Phase 5 builds the queue.

    Publishing is also what schedules the RAG ingest: the chatbot may quote a
    course the moment students can enrol in it, and not before.
    """
    course = await courses_service.submit_for_review(
        session, course_id, current_user, queue
    )
    return CourseOut.model_validate(course)


@router.post("/{course_id}/unpublish", response_model=CourseOut)
async def unpublish_course(
    course_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> CourseOut:
    """Pull a published course back to draft."""
    course = await courses_service.unpublish(session, course_id, current_user)
    return CourseOut.model_validate(course)
