"""`scripts.purge_e2e`: what the Playwright suite leaves behind, and only that.

The suite runs against a developer's own database, so the purge has to find
exactly its rows -- every account under the suite's domain and the courses they
wrote -- through five RESTRICT foreign keys, and leave everything else alone.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category, Certificate, Course, Enrollment, Order, OrderItem, User
from app.services import certificates
from scripts.purge_e2e import E2E_DOMAIN, count, purge


def person(role: str, *, suite: bool) -> User:
    domain = E2E_DOMAIN if suite else "@example.com"
    return User(
        email=f"{role}-{uuid.uuid4().hex[:8]}{domain}",
        full_name=role.title(),
        password_hash="x",
        role=role,
    )


async def world(session: AsyncSession) -> dict:
    """One run's worth of suite rows, beside rows that belong to nobody's test."""
    suite_teacher = person("instructor", suite=True)
    suite_student = person("student", suite=True)
    teacher = person("instructor", suite=False)
    student = person("student", suite=False)
    session.add_all([suite_teacher, suite_student, teacher, student])
    await session.flush()

    category = Category(
        name=f"Dọn E2E {uuid.uuid4().hex[:6]}", slug=f"don-e2e-{uuid.uuid4().hex[:6]}"
    )
    session.add(category)
    await session.flush()

    def course(owner: User, title: str) -> Course:
        return Course(
            instructor_id=owner.id,
            category_id=category.id,
            title=title,
            slug=f"{title.lower().replace(' ', '-')}-{uuid.uuid4().hex[:6]}",
            price=Decimal("199000"),
            status="published",
            published_at=datetime.now(UTC),
        )

    suite_course = course(suite_teacher, "Khoa E2E")
    kept_course = course(teacher, "Khoa That")
    session.add_all([suite_course, kept_course])
    await session.flush()

    bought = Enrollment(user_id=suite_student.id, course_id=suite_course.id, source="purchase")
    joined = Enrollment(user_id=suite_student.id, course_id=kept_course.id, source="free")
    # Somebody real bought the suite's course too -- it was on sale.
    stray = Enrollment(user_id=student.id, course_id=suite_course.id, source="purchase")
    kept = Enrollment(user_id=student.id, course_id=kept_course.id, source="free")
    session.add_all([bought, joined, stray, kept])
    await session.flush()
    kept_course.students_count = 2

    for buyer in (suite_student, student):
        order = Order(
            user_id=buyer.id,
            code=f"DP261002{uuid.uuid4().hex[:6].upper()}",
            subtotal=Decimal("199000"),
            total=Decimal("199000"),
        )
        session.add(order)
        await session.flush()
        session.add(
            OrderItem(order_id=order.id, course_id=suite_course.id, unit_price=Decimal("199000"))
        )

    session.add(
        Certificate(
            enrollment_id=bought.id,
            code=certificates.new_code(),
            recipient_name="Học Viên",
            course_title=suite_course.title,
            instructor_name="Giảng Viên",
            issued_at=datetime.now(UTC),
        )
    )
    await session.flush()
    return {
        "suite_course": suite_course.id,
        "kept_course": kept_course.id,
        "student": student.id,
        "teacher": teacher.id,
    }


async def test_the_suites_rows_go_and_nothing_else_does(db_session: AsyncSession) -> None:
    ids = await world(db_session)
    assert await count(db_session) >= (2, 1)

    purged = await purge(db_session)

    assert purged.courses >= 1
    assert purged.certificates >= 1
    assert await count(db_session) == (0, 0)
    assert await db_session.get(Course, ids["suite_course"]) is None
    # Every order that sold the suite's course is gone -- a line pointing at a
    # deleted course cannot stay -- and nothing else is.
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(OrderItem)
            .where(OrderItem.course_id == ids["suite_course"])
        )
        == 0
    )
    assert await db_session.get(User, ids["student"]) is not None
    assert await db_session.get(User, ids["teacher"]) is not None
    kept_course = await db_session.get(Course, ids["kept_course"])
    assert kept_course is not None


async def test_courses_the_suite_had_joined_are_recounted(db_session: AsyncSession) -> None:
    ids = await world(db_session)

    await purge(db_session)

    kept_course = await db_session.get(Course, ids["kept_course"])
    await db_session.refresh(kept_course)
    assert kept_course.students_count == 1
    assert (
        await db_session.scalar(
            select(func.count()).select_from(Order).where(Order.user_id == ids["student"])
        )
        == 0
    )


async def test_a_second_purge_finds_nothing(db_session: AsyncSession) -> None:
    await world(db_session)
    await purge(db_session)

    again = await purge(db_session)

    assert (again.users, again.courses, again.orders, again.certificates) == (0, 0, 0, 0)
