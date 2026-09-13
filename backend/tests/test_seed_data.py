"""The seeded catalogue.

Every course after this point is demoed on this data, and the failures worth
catching are the quiet ones: a category slug renamed in one list but not the
other, a title longer than its column, two lessons that would collide on the
same storage key. All of them break the seed on a pristine database only --
which is CI, or a teammate's first afternoon on the project.

Almost all of it runs without a database. The exception is at the bottom: the
code exercise is built by a branch of the seed that a static check cannot
reach, and it is the one piece the Phase 3 demo cannot do without.
"""

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    CodeExercise,
    Course,
    CourseSection,
    Lesson,
    TestCase,
    VideoAsset,
)
from app.schemas.auth import LoginIn
from scripts.seed import CATEGORY_TREE, seed_categories
from scripts.seed_courses import COURSES, INSTRUCTORS, seed_courses

# The three the plan asks for; there are four so the catalogue has something to
# filter and the price filter has a paid course to find.
MINIMUM_COURSES = 3


def category_slugs() -> set[str]:
    slugs = set()
    for _, slug, children in CATEGORY_TREE:
        slugs.add(slug)
        slugs.update(child_slug for _, child_slug in children)
    return slugs


def test_the_catalogue_has_enough_courses_to_demo_on() -> None:
    assert len(COURSES) >= MINIMUM_COURSES
    assert len({course.slug for course in COURSES}) == len(COURSES)


def test_every_course_points_at_a_category_and_an_instructor_that_exist() -> None:
    """The two lists live in different files and drift apart silently."""
    known_categories = category_slugs()
    known_instructors = {instructor.email for instructor in INSTRUCTORS}

    for course in COURSES:
        assert course.category_slug in known_categories, course.slug
        assert course.instructor_email in known_instructors, course.slug


@pytest.mark.parametrize("course", COURSES, ids=lambda course: course.slug)
def test_a_course_fits_the_columns_it_is_written_into(course) -> None:
    assert len(course.title) <= 200
    assert len(course.slug) <= 220
    assert len(course.subtitle) <= 300

    for section in course.sections:
        assert len(section.title) <= 200
        for lesson in section.lessons:
            assert len(lesson.title) <= 200


@pytest.mark.parametrize("course", COURSES, ids=lambda course: course.slug)
def test_a_course_is_a_real_curriculum(course) -> None:
    """Sections, video, and exactly one free sample -- what the page draws."""
    assert course.sections, "a course with no sections is not a course"

    videos = 0
    previews = 0

    for section in course.sections:
        assert section.lessons, f"{section.title} has no lessons"
        for lesson in section.lessons:
            videos += int(lesson.type == "video")
            previews += int(lesson.preview)

    assert videos > 0, "the plan asks for courses with video"
    # More than one free sample and the paid course gives itself away; none and
    # a visitor has nothing to judge it by.
    assert previews == 1


@pytest.mark.parametrize("course", COURSES, ids=lambda course: course.slug)
def test_a_lesson_is_either_a_video_with_a_length_or_an_article_with_text(
    course,
) -> None:
    for section in course.sections:
        for lesson in section.lessons:
            if lesson.type == "video":
                # duration_total_s is summed from these, and a zero would make
                # the course claim it is shorter than it is.
                assert lesson.duration_s > 0, lesson.title
                assert lesson.article is None
            elif lesson.type == "code_exercise":
                # Its content is the exercise, which lives in its own tables.
                assert lesson.exercise is not None, lesson.title
                assert lesson.article is None, lesson.title
                assert lesson.duration_s == 0, lesson.title
            else:
                assert lesson.article, lesson.title
                assert lesson.duration_s == 0, lesson.title


def test_no_two_lessons_would_claim_the_same_storage_key() -> None:
    """`uq_video_assets_storage_key` would reject the second one mid-seed."""
    keys = [
        f"seed/{course.slug}/{section_position}-{lesson_position}.mp4"
        for course in COURSES
        for section_position, section in enumerate(course.sections)
        for lesson_position, lesson in enumerate(section.lessons)
        if lesson.type == "video"
    ]

    assert len(set(keys)) == len(keys)


def test_a_course_knows_how_long_it_is() -> None:
    for course in COURSES:
        expected = sum(
            lesson.duration_s
            for section in course.sections
            for lesson in section.lessons
        )
        assert course.duration_total_s == expected
        assert course.duration_total_s > 0


def test_every_seeded_account_can_be_typed_into_the_login_form() -> None:
    """The seed writes users straight into the table, so nothing on the way in
    checks the address against the rule `/auth/login` applies on the way back.

    `.local` is on email-validator's special-use list, and a seed that uses it
    hands you three accounts the API answers 422 for -- found by deploying the
    production stack and trying to sign in as the seeded instructor, which is
    Chặng 8 of the demo script.
    """
    from scripts.seed import DEFAULT_ADMIN_EMAIL

    addresses = [DEFAULT_ADMIN_EMAIL] + [
        instructor.email for instructor in INSTRUCTORS
    ]

    for address in addresses:
        LoginIn(email=address, password="whatever-the-password-is")


# --- The one thing that does need a database -------------------------------


async def test_the_seed_really_writes_the_code_exercise_and_its_cases(
    db_session: AsyncSession,
) -> None:
    """Building an exercise is the only seed path a static check cannot cover.

    The seed skips a course whose slug is already there, so on a machine that
    has seeded once the new lesson would silently never be created -- and the
    first sign of it would be an empty exercise page during the Phase 3 demo.
    This deletes the course inside the test transaction, seeds it again for
    real, and rolls the whole thing back.
    """
    python_course = next(
        course for course in COURSES if course.category_slug == "python"
    )
    exercise_lessons = [
        lesson
        for section in python_course.sections
        for lesson in section.lessons
        if lesson.exercise is not None
    ]
    assert exercise_lessons, "the demo needs at least one code exercise to submit to"

    existing = await db_session.scalar(
        select(Course).where(Course.slug == python_course.slug)
    )
    if existing is not None:
        await db_session.delete(existing)
        # The video assets do not go with it: `lessons.video_asset_id` is SET
        # NULL, deliberately, so losing a video does not delete the lesson and
        # shift everything after it. They have to be cleared by hand here or
        # the reseed collides on `uq_video_assets_storage_key` -- which is the
        # difference between this and a pristine database, and the only part
        # of "pristine" a test transaction cannot arrange by itself.
        await db_session.execute(
            delete(VideoAsset).where(
                VideoAsset.storage_key.startswith(f"seed/{python_course.slug}/")
            )
        )
        await db_session.flush()

    # `seed_courses` looks its categories up rather than creating them, so
    # `main()` runs `seed_categories` first. Doing the same here is the whole
    # difference between a test that passes on a database someone has already
    # seeded and one that passes on an empty one -- and CI's is empty.
    await seed_categories(db_session)

    await seed_courses(db_session)

    course = await db_session.scalar(
        select(Course).where(Course.slug == python_course.slug)
    )
    lesson = await db_session.scalar(
        select(Lesson)
        .join(CourseSection, CourseSection.id == Lesson.section_id)
        .where(CourseSection.course_id == course.id, Lesson.type == "code_exercise")
    )
    assert lesson is not None

    exercise = await db_session.scalar(
        select(CodeExercise).where(CodeExercise.lesson_id == lesson.id)
    )
    assert exercise is not None
    assert exercise.language == "python"

    cases = list(
        await db_session.scalars(
            select(TestCase)
            .where(TestCase.exercise_id == exercise.id)
            .order_by(TestCase.position)
        )
    )
    spec = exercise_lessons[0].exercise
    assert [case.position for case in cases] == list(range(len(spec.cases)))
    # Samples first, and at least one of each kind: an exercise with no visible
    # case gives a student nothing to debug against, and one with no hidden
    # case is answered by pasting the expected output.
    assert [case.is_hidden for case in cases] == [case.hidden for case in spec.cases]
    assert not cases[0].is_hidden
    assert any(case.is_hidden for case in cases)
