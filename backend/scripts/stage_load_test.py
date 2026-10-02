"""A class of students, ready to be pointed at one code exercise at once.

    python -m scripts.stage_load_test [--students 20] [--cases 5] > stage.json

The load test (infra/loadtest/) sends every student's submission at the same
moment, through nginx and the public API, and waits for each verdict on the
same WebSocket the page listens on. What it needs beforehand is not part of
what it measures: a published course with one exercise, and that many enrolled
students who are already signed in.

Written straight into the tables, the way `bench_grading` does it, rather than
through the API: twenty sign-ups from one address is past the sign-up limit
(50 an hour per address) by the third run, and twenty sign-ins are a fifth of
the per-address sign-in budget. Signing in is not what is being measured, so
each student gets an access token minted with the API's own key -- the same
token the sign-in would have handed out, valid for two hours so that it
outlives a long run.

Every account is under the end-to-end suite's domain, so the same
`python -m scripts.purge_e2e` that cleans up after Playwright removes all of it
-- the course, the submissions, the XP -- in one go.

The course has a reading lesson ahead of the exercise on purpose. Accepted on a
one-lesson course, every submission would also finish the course and queue a
certificate PDF, and twenty WeasyPrint renders on the default queue are not
part of a class doing an exercise.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.core.security import create_access_token
from app.models import (
    Category,
    CodeExercise,
    Course,
    CourseSection,
    Enrollment,
    Lesson,
    TestCase,
    User,
)
from scripts.purge_e2e import E2E_DOMAIN

#: The answer every student sends. Trivial on purpose: what is measured is the
#: machinery around a program, not the program -- same as `bench_grading`.
SOLUTION = "a, b = input().split()\nprint(int(a) + int(b))\n"

TOKEN_LIFETIME = timedelta(hours=2)

#: Not a bcrypt hash, so no password signs in as these accounts -- the
#: checker reads an unreadable hash as a wrong password, not as an error. The
#: column cannot be empty for an account without Google (`ck_users_credential`).
NO_PASSWORD = "!"


@dataclass(frozen=True)
class Student:
    email: str
    token: str


@dataclass(frozen=True)
class Staged:
    course_slug: str
    lesson_id: str
    exercise_id: str
    cases: int
    solution: str
    students: list[Student]


async def stage(session: AsyncSession, *, students: int, cases: int) -> Staged:
    """Add the class to the session. Does not commit; the caller does."""
    category_id = await session.scalar(select(Category.id).order_by(Category.name).limit(1))
    if category_id is None:
        raise SystemExit("Chưa có danh mục nào -- chạy `python -m scripts.seed` trước.")

    tag = uuid.uuid4().hex[:6]
    teacher = User(
        email=f"load-giangvien-{tag}{E2E_DOMAIN}",
        full_name="Giảng Viên Load Test",
        password_hash=NO_PASSWORD,
        role="instructor",
    )
    session.add(teacher)
    await session.flush()

    course = Course(
        instructor_id=teacher.id,
        category_id=category_id,
        title=f"Load test chấm bài {tag}",
        slug=f"load-test-cham-bai-{tag}",
        price=Decimal("0"),
        status="published",
        published_at=datetime.now(UTC),
    )
    session.add(course)
    await session.flush()

    section = CourseSection(course_id=course.id, title="Chương 1", position=0)
    session.add(section)
    await session.flush()

    reading = Lesson(
        section_id=section.id,
        title="Đọc trước khi làm",
        type="article",
        article_content="`input().split()` tách một dòng thành các phần.",
        position=0,
    )
    exercise_lesson = Lesson(
        section_id=section.id, title="Tổng hai số", type="code_exercise", position=1
    )
    session.add_all([reading, exercise_lesson])
    await session.flush()

    exercise = CodeExercise(
        lesson_id=exercise_lesson.id,
        statement_md="Đọc hai số nguyên trên một dòng, in ra tổng.",
        starter_code="a, b = input().split()\n",
        language="python",
        time_limit_ms=2000,
        memory_limit_mb=128,
    )
    session.add(exercise)
    await session.flush()

    # Half visible, half hidden, as in `bench_grading`: the worker runs both
    # the same way, and the numbers stay comparable with Phase 3's.
    session.add_all(
        TestCase(
            exercise_id=exercise.id,
            position=index,
            input=f"{index} {index + 1}",
            expected_output=f"{index * 2 + 1}\n",
            is_hidden=index >= cases // 2,
            score_weight=1,
        )
        for index in range(cases)
    )

    people = [
        User(
            email=f"load-hocvien-{index:02d}-{tag}{E2E_DOMAIN}",
            full_name=f"Học Viên Load {index:02d}",
            password_hash=NO_PASSWORD,
            role="student",
        )
        for index in range(1, students + 1)
    ]
    session.add_all(people)
    await session.flush()
    session.add_all(
        Enrollment(user_id=person.id, course_id=course.id, source="free") for person in people
    )
    course.students_count = students
    await session.flush()

    return Staged(
        course_slug=course.slug,
        lesson_id=str(exercise_lesson.id),
        exercise_id=str(exercise.id),
        cases=cases,
        solution=SOLUTION,
        students=[
            Student(
                email=person.email,
                token=create_access_token(person.id, person.role, expires_in=TOKEN_LIFETIME),
            )
            for person in people
        ],
    )


async def main(students: int, cases: int) -> None:
    async with SessionLocal() as session:
        staged = await stage(session, students=students, cases=cases)
        await session.commit()

    # stdout is the hand-off to k6; anything said to a person goes to stderr.
    json.dump(asdict(staged), sys.stdout, ensure_ascii=False, indent=2)
    print(
        f"Đã dựng khóa {staged.course_slug}: {students} học viên, {cases} test case. "
        "Dọn bằng `python -m scripts.purge_e2e`.",
        file=sys.stderr,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--students", type=int, default=20)
    parser.add_argument("--cases", type=int, default=5)
    args = parser.parse_args()
    asyncio.run(main(args.students, args.cases))
