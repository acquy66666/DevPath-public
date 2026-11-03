"""The extra demo catalogue (`scripts.seed_catalogue`).

The plan is checked without a database first -- slugs that collide with
another seed, a category nobody writes, a catalogue that would not actually
vary -- then written and purged inside one rolled-back transaction.
"""

from collections import Counter

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category, Course, CourseSection, VideoAsset
from scripts.seed import CATEGORY_TREE, seed_categories
from scripts.seed_catalogue import CATEGORIES, COURSES, purge, seed_catalogue
from scripts.seed_courses import COURSES as REAL_COURSES
from scripts.seed_courses import seed_course_id, seed_courses
from scripts.seed_interactions import SYNTHETIC_COURSES

BASE_CATEGORY_SLUGS = {slug for _, slug, _ in CATEGORY_TREE} | {
    child for _, _, children in CATEGORY_TREE for _, child in children
}


def test_no_slug_is_shared_with_another_seed() -> None:
    slugs = [course.slug for course in COURSES]
    assert len(slugs) == len(set(slugs))
    others = {c.slug for c in REAL_COURSES} | {c.slug for c in SYNTHETIC_COURSES}
    assert not set(slugs) & others


def test_every_category_is_written_by_this_seed_or_the_base_one() -> None:
    own = {category.slug for category in CATEGORIES}
    assert not own & BASE_CATEGORY_SLUGS
    seen: set[str] = set()
    for category in CATEGORIES:
        if category.parent_slug is not None:
            assert category.parent_slug in seen | BASE_CATEGORY_SLUGS
        seen.add(category.slug)
    for course in COURSES:
        assert course.category_slug in own | BASE_CATEGORY_SLUGS


def test_the_catalogue_varies_where_the_filters_look() -> None:
    """What the page is for: every level, free and paid, many categories."""
    levels = Counter(course.level for course in COURSES)
    assert set(levels) == {"beginner", "intermediate", "advanced"}
    assert any(course.price == 0 for course in COURSES)
    assert len({course.price for course in COURSES}) >= 8
    assert len({course.category_slug for course in COURSES}) >= 12


def test_every_course_opens_with_a_preview_and_has_an_article() -> None:
    for course in COURSES:
        assert len(course.sections) >= 2, course.slug
        assert course.sections[0].lessons[0].preview, course.slug
        assert any(
            lesson.type == "article"
            for section in course.sections
            for lesson in section.lessons
        ), course.slug


@pytest.fixture
async def base(db_session: AsyncSession) -> None:
    await seed_categories(db_session)
    await seed_courses(db_session)
    await db_session.flush()


async def test_it_writes_the_courses_published_with_fixed_ids(
    db_session: AsyncSession, base: None
) -> None:
    await seed_catalogue(db_session)

    rows = {
        course.slug: course
        for course in await db_session.scalars(
            select(Course).where(Course.slug.in_([c.slug for c in COURSES]))
        )
    }
    assert set(rows) == {c.slug for c in COURSES}
    for slug, course in rows.items():
        assert course.id == seed_course_id(slug)
        assert course.status == "published"
        assert course.published_at is not None

    again = await seed_catalogue(db_session)
    assert again.courses == 0
    assert again.categories == 0


async def test_purge_takes_back_everything_it_wrote(
    db_session: AsyncSession, base: None
) -> None:
    # On a machine where the script already ran, purge it first so "before"
    # means the base seed alone.
    await purge(db_session)
    before = {
        "courses": await db_session.scalar(select(func.count()).select_from(Course)),
        "categories": await db_session.scalar(
            select(func.count()).select_from(Category)
        ),
        "videos": await db_session.scalar(select(func.count()).select_from(VideoAsset)),
        "sections": await db_session.scalar(
            select(func.count()).select_from(CourseSection)
        ),
    }

    await seed_catalogue(db_session)
    await purge(db_session)

    after = {
        "courses": await db_session.scalar(select(func.count()).select_from(Course)),
        "categories": await db_session.scalar(
            select(func.count()).select_from(Category)
        ),
        "videos": await db_session.scalar(select(func.count()).select_from(VideoAsset)),
        "sections": await db_session.scalar(
            select(func.count()).select_from(CourseSection)
        ),
    }
    assert after == before
