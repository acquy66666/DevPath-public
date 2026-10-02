"""`scripts.stage_load_test`: a class ready to submit, and gone again after.

The load test trusts this script for three things it cannot check from the
outside: every token signs in as an enrolled student of the staged course, the
exercise has the cases the report says it has, and `purge_e2e` takes all of it
back off the database.
"""

import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token, verify_password
from app.models import Course, Enrollment, Lesson, TestCase, User
from scripts.purge_e2e import E2E_DOMAIN, count, purge
from scripts.stage_load_test import NO_PASSWORD, stage


async def test_every_token_is_an_enrolled_student(db_session: AsyncSession) -> None:
    staged = await stage(db_session, students=3, cases=4)

    course = await db_session.scalar(select(Course).where(Course.slug == staged.course_slug))
    assert course is not None
    assert course.status == "published"
    assert len(staged.students) == 3

    for student in staged.students:
        assert student.email.endswith(E2E_DOMAIN)
        payload = decode_access_token(student.token)
        user = await db_session.get(User, payload.user_id)
        assert user is not None
        assert user.email == student.email
        assert user.role == payload.role == "student"
        enrolled = await db_session.scalar(
            select(func.count())
            .select_from(Enrollment)
            .where(Enrollment.user_id == user.id, Enrollment.course_id == course.id)
        )
        assert enrolled == 1


async def test_the_exercise_has_the_cases_asked_for(db_session: AsyncSession) -> None:
    staged = await stage(db_session, students=1, cases=5)

    cases = list(
        await db_session.scalars(
            select(TestCase)
            .where(TestCase.exercise_id == uuid.UUID(staged.exercise_id))
            .order_by(TestCase.position)
        )
    )
    assert len(cases) == 5
    assert [case.is_hidden for case in cases] == [False, False, True, True, True]
    # The solution every student sends is right on every case, or the run
    # would be measuring wrong answers.
    for case in cases:
        a, b = case.input.split()
        assert f"{int(a) + int(b)}\n" == case.expected_output

    # A reading lesson comes first, so an accepted exercise does not finish
    # the course and queue a certificate for every student.
    exercise_lesson = await db_session.get(Lesson, uuid.UUID(staged.lesson_id))
    assert exercise_lesson is not None
    assert exercise_lesson.type == "code_exercise"
    lessons = list(
        await db_session.scalars(
            select(Lesson.type)
            .where(Lesson.section_id == exercise_lesson.section_id)
            .order_by(Lesson.position)
        )
    )
    assert lessons == ["article", "code_exercise"]


@pytest.mark.parametrize("attempt", ["", "!", "mat-khau-bat-ky"])
def test_no_password_signs_in(attempt: str) -> None:
    assert verify_password(attempt, NO_PASSWORD) is False


async def test_purge_e2e_takes_it_all_back(db_session: AsyncSession) -> None:
    staged = await stage(db_session, students=4, cases=2)

    purged = await purge(db_session)

    assert purged.users >= 5  # four students and their teacher
    assert purged.courses >= 1
    assert await count(db_session) == (0, 0)
    assert (
        await db_session.scalar(select(Course.id).where(Course.slug == staged.course_slug)) is None
    )
