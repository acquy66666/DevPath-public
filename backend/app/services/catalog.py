"""The public catalogue: search, filter, sort, paginate.

Kept apart from `courses.py`, which is about one course and who owns it. This
module never edits anything and never sees a draft -- every query starts from
"published, not deleted" and narrows from there.

On the search itself: the vector is built by a trigger (revision
`0c55c726cc39`) with the `simple` configuration over `unaccent`-ed text, so the
query side has to spell it the same way or "lap trinh" never meets "lập trình".
That pairing lives in `_tsquery` below and nowhere else.
"""

import uuid
from decimal import Decimal
from typing import Literal

from sqlalchemy import ColumnElement, Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category, Course, User

Sort = Literal["relevance", "newest", "rating"]

# Long enough for a sentence, short enough that nobody posts a novel to a GET.
MAX_QUERY_LENGTH = 200


def _tsquery(text: str) -> ColumnElement:
    """The reader's words, in the shape the stored vector was written in.

    `websearch_to_tsquery` rather than `plainto_tsquery` because it understands
    what people already type into search boxes -- a quoted "vòng lặp" as a
    phrase, `-python` to exclude -- and never raises on punctuation the way
    `to_tsquery` does.
    """
    return func.websearch_to_tsquery("simple", func.unaccent(text))


def search_filter(text: str) -> ColumnElement[bool]:
    """Rows whose search vector matches the reader's words."""
    return Course.search_vector.op("@@")(_tsquery(text))


def _relevance(text: str) -> ColumnElement:
    """How well a row matches, with the trigger's A/B/C weights applied."""
    return func.ts_rank(Course.search_vector, _tsquery(text))


async def _category_and_children(
    session: AsyncSession, category_id: uuid.UUID
) -> list[uuid.UUID]:
    """The category asked for, plus the ones nested under it.

    Picking "Lập trình" has to include "Python": a parent category is a heading
    in this taxonomy, and courses hang off the leaves. The tree is two levels
    deep by design, so one query is the whole of it.

    An id that matches nothing comes back as itself and simply finds no
    courses. A catalogue answering 404 to a stale bookmark would be worse than
    one answering "không có khóa học nào".
    """
    children = await session.scalars(
        select(Category.id).where(Category.parent_id == category_id)
    )
    return [category_id, *children]


def _ordering(sort: Sort, q: str | None) -> list[ColumnElement]:
    if sort == "relevance" and q:
        # Newest breaks ties: two equally relevant courses should not swap
        # places between page loads.
        return [_relevance(q).desc(), Course.published_at.desc()]
    if sort == "rating":
        # Count second: 5.00 from one review should not outrank 4.80 from two
        # hundred, and this is the cheap half of that fix. The honest one is a
        # Bayesian average, which needs more reviews than Phase 2 has.
        return [Course.rating_avg.desc(), Course.rating_count.desc()]
    return [Course.published_at.desc()]


async def list_published(
    session: AsyncSession,
    *,
    q: str | None = None,
    category_id: uuid.UUID | None = None,
    price_min: Decimal | None = None,
    price_max: Decimal | None = None,
    rating_min: Decimal | None = None,
    sort: Sort | None = None,
    page: int,
    page_size: int,
) -> tuple[list[tuple[Course, User, Category]], int]:
    """One page of the catalogue, with each course's instructor and category.

    Returns the rows and the total before paging, because the client draws
    "trang 2 / 7" and cannot count what it was not sent.
    """
    text = (q or "").strip()
    conditions: list[ColumnElement[bool]] = [
        Course.deleted_at.is_(None),
        Course.status == "published",
    ]

    if text:
        conditions.append(search_filter(text))
    if category_id is not None:
        conditions.append(
            Course.category_id.in_(await _category_and_children(session, category_id))
        )
    if price_min is not None:
        conditions.append(Course.price >= price_min)
    if price_max is not None:
        conditions.append(Course.price <= price_max)
    if rating_min is not None:
        conditions.append(Course.rating_avg >= rating_min)

    # Searching and then sorting by date hides the best match on page four, so
    # a query with words defaults to relevance and a bare listing to newest.
    effective_sort: Sort = sort or ("relevance" if text else "newest")

    # Counted on `courses` alone: both joins below are inner joins on NOT NULL
    # foreign keys with ON DELETE RESTRICT, so neither can drop a row or
    # duplicate one, and counting without them is a smaller query.
    total = await session.scalar(
        select(func.count()).select_from(Course).where(*conditions)
    )

    listing: Select[tuple[Course, User, Category]] = (
        select(Course, User, Category)
        .join(User, User.id == Course.instructor_id)
        .join(Category, Category.id == Course.category_id)
        .where(*conditions)
        .order_by(*_ordering(effective_sort, text or None))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    rows = (await session.execute(listing)).all()
    return [tuple(row) for row in rows], total or 0
