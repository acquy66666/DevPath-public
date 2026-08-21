"""Turning a Vietnamese course title into a URL."""

import re

from app.services.slug import SLUG_MAX_LENGTH, slugify, unique_slug


def test_a_plain_title_becomes_a_plain_slug() -> None:
    assert slugify("Python co ban") == "python-co-ban"


def test_vietnamese_tones_are_stripped_not_dropped() -> None:
    """`unicodedata` alone turns "đ" into nothing; a Vietnamese slug needs it."""
    assert slugify("Lập trình Python cơ bản") == "lap-trinh-python-co-ban"


def test_the_letter_d_with_a_stroke_survives_as_d() -> None:
    assert slugify("Đường đi ngắn nhất") == "duong-di-ngan-nhat"


def test_punctuation_and_runs_of_spaces_collapse() -> None:
    assert slugify("  C++,   C#  &  Java!  ") == "c-c-java"


def test_a_title_of_only_symbols_still_produces_something_usable() -> None:
    """A slug is part of a URL; empty is not an option."""
    assert slugify("!!! ??? ...") == "khoa-hoc"


def test_the_slug_fits_the_column() -> None:
    """courses.slug is VARCHAR(220) and titles run to 200 characters."""
    slug = unique_slug("Khóa học " + "dài " * 100)

    assert len(slug) <= SLUG_MAX_LENGTH


def test_a_unique_slug_keeps_the_readable_part() -> None:
    slug = unique_slug("Lập trình Python cơ bản")

    assert slug.startswith("lap-trinh-python-co-ban-")


def test_two_courses_may_share_a_title_without_sharing_a_url() -> None:
    """The suffix is what makes the unique index on slug survive real life."""
    slugs = {unique_slug("Lập trình Python cơ bản") for _ in range(50)}

    assert len(slugs) == 50


def test_a_slug_contains_only_url_safe_characters() -> None:
    slug = unique_slug("Kỹ thuật: Lập trình C++ (nâng cao) — 2026!")

    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", slug)
