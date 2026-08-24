"""The seeded catalogue, checked without touching a database.

Every course after this point is demoed on this data, and the failures worth
catching are the quiet ones: a category slug renamed in one list but not the
other, a title longer than its column, two lessons that would collide on the
same storage key. All of them break the seed on a pristine database only --
which is CI, or a teammate's first afternoon on the project.
"""

import pytest

from scripts.seed import CATEGORY_TREE
from scripts.seed_courses import COURSES, INSTRUCTORS

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
