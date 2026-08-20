"""Metadata tests for the first three tables.

These run without a database: they check that the models say what
docs/database-design.md says. The migration itself is verified by running
upgrade/downgrade against the dev database.
"""

import pytest

from app.models import Base, Category, Course, User


def constraint_names(model: type) -> set[str]:
    return {c.name for c in model.__table__.constraints if c.name}


def index_names(model: type) -> set[str]:
    return {i.name for i in model.__table__.indexes}


def test_all_three_tables_are_registered() -> None:
    assert set(Base.metadata.tables) == {"users", "categories", "courses"}


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
