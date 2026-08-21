"""Metadata tests for the first three tables.

These run without a database: they check that the models say what
docs/database-design.md says. The migration itself is verified by running
upgrade/downgrade against the dev database.
"""

import pytest

from app.models import (
    Base,
    Category,
    Course,
    CourseSection,
    Lesson,
    RefreshToken,
    User,
    VideoAsset,
)


def constraint_names(model: type) -> set[str]:
    return {c.name for c in model.__table__.constraints if c.name}


def index_names(model: type) -> set[str]:
    return {i.name for i in model.__table__.indexes}


def test_registered_tables_match_the_phases_done_so_far() -> None:
    """Phase 1 created three; Phase 2 adds auth sessions and the curriculum."""
    assert set(Base.metadata.tables) == {
        "users",
        "categories",
        "courses",
        "refresh_tokens",
        "course_sections",
        "lessons",
        "video_assets",
    }


@pytest.mark.parametrize("model", [User, Category, Course])
def test_every_table_has_uuid_pk_and_timestamps(model: type) -> None:
    table = model.__table__
    assert [c.name for c in table.primary_key.columns] == ["id"]
    assert table.c.created_at.nullable is False
    assert table.c.updated_at.nullable is False


def test_users_constraints_match_the_spec() -> None:
    assert {"ck_users_role", "ck_users_credential"} <= constraint_names(User)
    assert {"uq_users_email", "uq_users_oauth", "ix_users_role"} == index_names(User)


def test_users_oauth_index_is_partial() -> None:
    """A unique index over two nullable columns would not constrain much."""
    index = next(i for i in User.__table__.indexes if i.name == "uq_users_oauth")
    assert index.unique is True
    assert "oauth_sub IS NOT NULL" in str(index.dialect_options["postgresql"]["where"])


def test_password_hash_is_optional_but_full_name_is_not() -> None:
    assert User.__table__.c.password_hash.nullable is True
    assert User.__table__.c.full_name.nullable is False


def test_categories_constraints_match_the_spec() -> None:
    assert "ck_categories_not_self_parent" in constraint_names(Category)
    assert {"uq_categories_slug", "ix_categories_parent_id"} == index_names(Category)


def test_category_parent_is_self_referential_and_restricted() -> None:
    fk = next(iter(Category.__table__.c.parent_id.foreign_keys))
    assert fk.column.table.name == "categories"
    assert fk.ondelete == "RESTRICT"


def test_courses_check_constraints_match_the_spec() -> None:
    expected = {
        "ck_courses_status",
        "ck_courses_level",
        "ck_courses_price_non_negative",
        "ck_courses_rating_range",
        "ck_courses_published_at",
        "ck_courses_rejection_reason",
    }
    assert expected <= constraint_names(Course)


def test_courses_indexes_match_the_spec() -> None:
    expected = {
        "uq_courses_slug",
        "ix_courses_listing",
        "ix_courses_rating",
        "ix_courses_search_vector",
        "ix_courses_category_id",
        "ix_courses_instructor_id",
    }
    assert expected == index_names(Course)


def test_listing_indexes_exclude_soft_deleted_rows() -> None:
    """Public queries always filter deleted_at IS NULL; the index must agree."""
    for name in ("ix_courses_listing", "ix_courses_rating"):
        index = next(i for i in Course.__table__.indexes if i.name == name)
        where = str(index.dialect_options["postgresql"]["where"])
        assert "deleted_at IS NULL" in where


def test_search_vector_index_is_gin() -> None:
    index = next(
        i for i in Course.__table__.indexes if i.name == "ix_courses_search_vector"
    )
    assert index.dialect_options["postgresql"]["using"] == "gin"


def test_money_and_rating_are_numeric_not_float() -> None:
    """Float money is a bug that shows up months later, in someone's invoice."""
    assert Course.__table__.c.price.type.python_type is __import__("decimal").Decimal
    assert Course.__table__.c.price.type.scale == 2
    assert Course.__table__.c.rating_avg.type.scale == 2


def test_course_owner_references_cannot_orphan_rows() -> None:
    for column in ("instructor_id", "category_id"):
        fk = next(iter(Course.__table__.c[column].foreign_keys))
        assert fk.ondelete == "RESTRICT"


def test_courses_is_the_only_soft_deleted_table() -> None:
    assert "deleted_at" in Course.__table__.c
    assert "deleted_at" not in User.__table__.c
    assert "deleted_at" not in Category.__table__.c


def test_refresh_tokens_indexes_match_the_spec() -> None:
    assert {"uq_refresh_tokens_token_hash", "ix_refresh_tokens_user_id"} == index_names(
        RefreshToken
    )


def test_refresh_token_hash_column_fits_sha256_hex() -> None:
    """Only the hash is stored: a leaked database must not yield usable tokens."""
    assert RefreshToken.__table__.c.token_hash.type.length == 64
    assert "token" not in {
        c.name for c in RefreshToken.__table__.columns if c.name != "token_hash"
    }


def test_deleting_a_user_takes_their_sessions_with_them() -> None:
    fk = next(iter(RefreshToken.__table__.c.user_id.foreign_keys))
    assert fk.column.table.name == "users"
    assert fk.ondelete == "CASCADE"


def test_refresh_token_records_expiry_and_revocation() -> None:
    table = RefreshToken.__table__
    assert table.c.expires_at.nullable is False
    assert table.c.revoked_at.nullable is True


def test_refresh_token_has_created_at_but_no_updated_at() -> None:
    """Deviates from the project-wide timestamp pair on purpose.

    docs/database-design.md gives this table `created_at` only: a session row
    is written once and then at most revoked, and `revoked_at` says when that
    happened more precisely than a generic `updated_at` would.
    """
    assert "created_at" in RefreshToken.__table__.c
    assert "updated_at" not in RefreshToken.__table__.c


def test_positions_are_unique_per_parent_and_deferrable() -> None:
    """Reordering rewrites several rows in one transaction.

    With an immediate constraint the second UPDATE collides with the first,
    before the arrangement the instructor asked for even exists.
    """
    for model, name in (
        (CourseSection, "uq_course_sections_position"),
        (Lesson, "uq_lessons_position"),
    ):
        constraint = next(
            c for c in model.__table__.constraints if c.name == name
        )
        assert constraint.deferrable is True
        assert constraint.initially == "DEFERRED"


def test_deleting_a_course_takes_its_curriculum_with_it() -> None:
    section_fk = next(iter(CourseSection.__table__.c.course_id.foreign_keys))
    lesson_fk = next(iter(Lesson.__table__.c.section_id.foreign_keys))

    assert section_fk.ondelete == "CASCADE"
    assert lesson_fk.ondelete == "CASCADE"


def test_losing_a_video_does_not_delete_the_lesson() -> None:
    """SET NULL: the lesson stays, its slot in the order stays, the video is gone."""
    fk = next(iter(Lesson.__table__.c.video_asset_id.foreign_keys))

    assert fk.ondelete == "SET NULL"


def test_only_video_lessons_may_carry_a_video() -> None:
    names = {c.name for c in Lesson.__table__.constraints if c.name}

    assert {"ck_lessons_type", "ck_lessons_video_asset_type"} <= names


def test_video_assets_are_keyed_by_their_storage_object() -> None:
    names = {c.name for c in VideoAsset.__table__.constraints if c.name}

    assert "uq_video_assets_storage_key" in names
    assert "ck_video_assets_status" in names
