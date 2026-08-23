"""Enrolling in a course, and the list of what you are enrolled in.

Both live here rather than in `courses.py` because they are about a person, not
about a course: every one of them answers only for the caller, and none of them
takes a user id to aim at somebody else.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.core.deps import CurrentUser, DbSession
from app.schemas.categories import CategoryOut
from app.schemas.courses import CourseCardBase, CourseCardOut, CourseInstructorOut
from app.schemas.enrollments import EnrolledCourseOut, EnrollmentOut
from app.schemas.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, Page
from app.services import enrollments as enrollments_service

router = APIRouter(tags=["enrollments"])


@router.post(
    "/courses/{course_id}/enroll",
    response_model=EnrollmentOut,
    status_code=status.HTTP_201_CREATED,
)
async def enrol_in_course(
    course_id: uuid.UUID,
    response: Response,
    current_user: CurrentUser,
    session: DbSession,
) -> EnrollmentOut:
    """Enrol yourself in a free published course.

    Answers 201 the first time and 200 afterwards: enrolling twice is the same
    fact, not an error, and a double click should not produce a scary message.

    A course with a price answers 409 `COURSE_NOT_FREE`. Paying for one is
    Phase 5, and this endpoint must not be the way around it.
    """
    enrollment, created = await enrollments_service.enrol_free(
        session, course_id, current_user
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return EnrollmentOut.model_validate(enrollment)


@router.get("/courses/{course_id}/enrollment", response_model=EnrollmentOut)
async def get_my_enrollment(
    course_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> EnrollmentOut:
    """Am I enrolled in this course? 404 `ENROLLMENT_NOT_FOUND` if not.

    The course page asks this from the browser rather than at render time: the
    page itself is server-rendered for everyone alike, and only the button
    changes with who is looking.
    """
    enrollment = await enrollments_service.get_for_course(
        session, course_id, current_user
    )
    return EnrollmentOut.model_validate(enrollment)


@router.get("/enrollments/me", response_model=Page[EnrolledCourseOut])
async def list_my_enrollments(
    current_user: CurrentUser,
    session: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
) -> Page[EnrolledCourseOut]:
    """"Khóa học của tôi" — newest enrolment first."""
    rows, total = await enrollments_service.list_for_user(
        session, current_user, page=page, page_size=page_size
    )

    return Page[EnrolledCourseOut](
        items=[
            EnrolledCourseOut(
                course=CourseCardOut(
                    **CourseCardBase.model_validate(course).model_dump(),
                    instructor=CourseInstructorOut.model_validate(instructor),
                    category=CategoryOut.model_validate(category),
                ),
                enrolled_at=enrollment.created_at,
                completed_at=enrollment.completed_at,
            )
            for enrollment, course, instructor, category in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )
