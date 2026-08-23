"""add_course_search_vector_trigger

Revision ID: 0c55c726cc39
Revises: f7d37ee5caf2
Create Date: 2026-08-23 14:33:31.152889

The column and its GIN index have existed since the first migration; what was
missing is the thing that fills them.

Three decisions are baked into the function below:

* **A trigger, not a generated column.** `unaccent()` is STABLE rather than
  IMMUTABLE -- it reads a dictionary file -- so Postgres refuses it inside a
  generated column or an index expression. A trigger computes the value once
  on write and stores it, which sidesteps that entirely and keeps every writer
  honest: no service can forget to update the vector.

* **The `simple` configuration, not `english`.** The text is Vietnamese.
  English stemming would turn "học" into noise and does nothing useful for a
  language that has no inflection; `simple` just lowercases and splits.

* **`unaccent` on both sides.** People type "lap trinh python" and expect the
  course called "Lập trình Python". The query side must apply the same
  function, or the two spellings never meet -- see `search_filter` in
  `app/services/catalog.py`.

Weights follow what a search is really looking for: the title carries A, the
subtitle B, the description C, and `ts_rank` reads them in that order.
"""
from collections.abc import Sequence

from alembic import op

revision: str = '0c55c726cc39'
down_revision: str | None = 'f7d37ee5caf2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Kept out of the function body so the shape of the vector is the first thing
# a reader sees. `NEW.` makes it trigger-only, which is why the backfill below
# fires the trigger instead of repeating this expression.
SEARCH_VECTOR_SQL = """
    setweight(to_tsvector('simple', unaccent(coalesce(NEW.title, ''))), 'A')
 || setweight(to_tsvector('simple', unaccent(coalesce(NEW.subtitle, ''))), 'B')
 || setweight(to_tsvector('simple', unaccent(coalesce(NEW.description, ''))), 'C')
"""


def upgrade() -> None:
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION courses_search_vector_refresh()
        RETURNS trigger AS $$
        BEGIN
            NEW.search_vector := {SEARCH_VECTOR_SQL};
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )

    # `UPDATE OF` applies to updates only -- an insert always runs the trigger.
    # Listing the three columns means editing a price or publishing a course
    # does not rebuild a vector that cannot have changed.
    op.execute(
        """
        CREATE TRIGGER courses_search_vector_update
        BEFORE INSERT OR UPDATE OF title, subtitle, description ON courses
        FOR EACH ROW EXECUTE FUNCTION courses_search_vector_refresh()
        """
    )

    # Backfill by touching the columns the trigger watches, rather than
    # repeating the expression: `SET title = title` fires a column-scoped
    # trigger because the column is in the SET list, whatever the value. It is
    # raw SQL, so SQLAlchemy's `onupdate` never runs and no `updated_at` moves.
    op.execute("UPDATE courses SET title = title")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS courses_search_vector_update ON courses")
    op.execute("DROP FUNCTION IF EXISTS courses_search_vector_refresh()")
    # The column stays -- it belongs to the first migration -- but its contents
    # would be stale the moment a course is edited without the trigger.
    op.execute("UPDATE courses SET search_vector = NULL")
