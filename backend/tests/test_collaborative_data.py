"""Where the collaborative filter's numbers come from: the real tables.

`test_collaborative.py` proves the arithmetic on hand-made triples. This file
proves the other half -- that an enrolment, a completion and a review in
Postgres become the weight the plan says they should, and that courses nobody
may be sent to never enter the matrix at all.

The dev database may already hold seed enrolments, and `load_interactions`
reads every row it can see. So nothing here asserts on the whole result: each
test looks only at the users and courses it created, which is also what makes
it safe to run against a database somebody is demoing from.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models import Category, Course, Enrollment, Review, User
from app.services.collaborative import fit, load_interactions

PASSWORD = "mật-khẩu-đủ-dài"


class World:
    """A category, an instructor, and helpers to fill a catalogue quickly."""

    def __init__(self, session: AsyncSession, category: Category, instructor: User):
        self.session = session
        self.category = category
        self.instructor = instructor

    async def course(
        self, title: str, *, status: str = "published", deleted: bool = False
    ) -> Course:
        course = Course(
            instructor_id=self.instructor.id,
            category_id=self.category.id,
            title=title,
            slug=f"{title.lower()}-{uuid.uuid4().hex[:8]}",
            price=Decimal("0"),
            status=status,
            published_at=datetime.now(UTC) if status == "published" else None,
            deleted_at=datetime.now(UTC) if deleted else None,
        )
        self.session.add(course)
        await self.session.flush()
        return course

    async def student(self, name: str) -> User:
        user = User(
            email=f"{name}-{uuid.uuid4().hex[:8]}@example.com",
            full_name=name,
            password_hash=hash_password(PASSWORD),
            role="student",
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def takes(
        self,
        user: User,
        course: Course,
        *,
        completed: bool = False,
        rating: int | None = None,
    ) -> None:
        self.session.add(
            Enrollment(
                user_id=user.id,
                course_id=course.id,
                completed_at=datetime.now(UTC) if completed else None,
            )
        )
        if rating is not None:
            self.session.add(Review(user_id=user.id, course_id=course.id, rating=rating))
        await self.session.flush()


async def make_world(db_session: AsyncSession) -> World:
    instructor = User(
        email=f"gv-{uuid.uuid4().hex[:8]}@example.com",
        full_name="Giảng viên",
        password_hash=hash_password(PASSWORD),
        role="instructor",
    )
    category = Category(name="Lập trình", slug=f"lap-trinh-{uuid.uuid4().hex[:8]}")
    db_session.add_all([instructor, category])
    await db_session.flush()
    return World(db_session, category, instructor)


async def weights_of(db_session: AsyncSession, user: User) -> dict[uuid.UUID, int]:
    return {
        row.course_id: row.weight
        for row in await load_interactions(db_session)
        if row.user_id == user.id
    }


async def test_enrolling_completing_and_rating_become_the_plan_s_weights(
    db_session: AsyncSession,
):
    world = await make_world(db_session)
    enrolled, completed, loved, disliked = [
        await world.course(title) for title in ("Enrolled", "Completed", "Loved", "Disliked")
    ]
    student = await world.student("hoc-vien")

    await world.takes(student, enrolled)
    await world.takes(student, completed, completed=True)
    await world.takes(student, loved, completed=True, rating=5)
    await world.takes(student, disliked, completed=True, rating=1)

    assert await weights_of(db_session, student) == {
        enrolled.id: 1,
        completed.id: 2,
        loved.id: 3,
        disliked.id: 1,
    }


async def test_courses_that_cannot_be_recommended_never_enter_the_matrix(
    db_session: AsyncSession,
):
    """A draft and a withdrawn course, both taken by someone.

    Kept out at the query rather than filtered from the output: once a course
    is in the matrix, every reader of the model has to remember to drop it.
    """
    world = await make_world(db_session)
    live = await world.course("Live")
    draft = await world.course("Draft", status="draft")
    withdrawn = await world.course("Withdrawn", deleted=True)
    student = await world.student("hoc-vien")

    for course in (live, draft, withdrawn):
        await world.takes(student, course)

    assert set(await weights_of(db_session, student)) == {live.id}


async def test_one_row_per_enrolment_even_with_a_review(db_session: AsyncSession):
    """The join to reviews must not multiply rows."""
    world = await make_world(db_session)
    course = await world.course("Reviewed")
    student = await world.student("hoc-vien")
    await world.takes(student, course, completed=True, rating=4)

    rows = [row for row in await load_interactions(db_session) if row.user_id == student.id]

    assert len(rows) == 1


async def test_from_the_tables_to_a_recommendation(db_session: AsyncSession):
    """The whole path, on a catalogue with two tastes in it.

    Three people take the Python track, three take the design track, and a
    newcomer has finished only the first Python course. The model is fitted on
    everything the loader returns -- seed data included, if the database has
    any -- and must still point the newcomer at the rest of their own track.
    """
    world = await make_world(db_session)
    py = [await world.course(f"Python{n}") for n in (1, 2, 3)]
    de = [await world.course(f"Design{n}") for n in (1, 2, 3)]

    for n in range(3):
        fan = await world.student(f"py-fan-{n}")
        for course in py:
            await world.takes(fan, course, completed=True)
    for n in range(3):
        fan = await world.student(f"design-fan-{n}")
        for course in de:
            await world.takes(fan, course, completed=True, rating=5)

    newcomer = await world.student("newcomer")
    await world.takes(newcomer, py[0], completed=True)

    model = fit(await load_interactions(db_session))
    recommended = model.recommend(newcomer.id, k=2)

    assert {r.course_id for r in recommended} == {py[1].id, py[2].id}
    assert all(r.because == py[0].id for r in recommended)
