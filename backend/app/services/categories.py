"""Reading the category tree.

Two levels deep by design (see `models/category.py`), so the whole thing is one
query and a grouping pass -- there is no recursion to write and no depth to
guard against.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category


async def list_tree(session: AsyncSession) -> list[tuple[Category, list[Category]]]:
    """Every category, parents first, each with its children in order.

    Ordered by `position` then `name`: position is what an admin arranges, and
    the name keeps rows that share a position from swapping places between two
    requests.
    """
    rows = list(
        await session.scalars(
            select(Category).order_by(Category.position, Category.name)
        )
    )

    children: dict = {}
    for row in rows:
        if row.parent_id is not None:
            children.setdefault(row.parent_id, []).append(row)

    return [(row, children.get(row.id, [])) for row in rows if row.parent_id is None]
