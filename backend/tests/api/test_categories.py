"""The category tree the course form picks from.

Assertions only ever look at the rows this test created: the development
database already holds the seeded tree, and a test that counted everything
would pass on a fresh database and fail on a real one.
"""

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category

CATEGORIES = "/api/v1/categories"


async def make_category(
    session: AsyncSession,
    name: str,
    *,
    parent: Category | None = None,
    position: int = 0,
) -> Category:
    category = Category(
        name=name,
        slug=f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}",
        parent_id=parent.id if parent else None,
        position=position,
    )
    session.add(category)
    await session.flush()
    return category


def find(payload: list[dict], category: Category) -> dict | None:
    return next((item for item in payload if item["id"] == str(category.id)), None)


async def test_lists_categories_without_signing_in(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Public: the course form needs it, and so will the catalogue filter."""
    category = await make_category(db_session, "Rust")

    response = await api_client.get(CATEGORIES)

    assert response.status_code == 200
    assert find(response.json(), category) is not None


async def test_children_are_nested_under_their_parent(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    parent = await make_category(db_session, "Di động")
    child = await make_category(db_session, "Flutter", parent=parent)

    payload = (await api_client.get(CATEGORIES)).json()

    branch = find(payload, parent)
    assert branch is not None
    assert [item["id"] for item in branch["children"]] == [str(child.id)]

    # And not a second time at the top level, where it would look like a
    # category of its own.
    assert find(payload, child) is None


async def test_children_come_back_in_position_order(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Position is what an admin arranges -- not insertion order, not the name.

    The names run the other way round on purpose: sorting them alphabetically
    would put "Airflow" first and this test would catch it.
    """
    parent = await make_category(db_session, "Dữ liệu")
    second = await make_category(db_session, "Airflow", parent=parent, position=1)
    first = await make_category(db_session, "Zarr", parent=parent, position=0)

    branch = find((await api_client.get(CATEGORIES)).json(), parent)

    assert branch is not None
    assert [item["id"] for item in branch["children"]] == [
        str(first.id),
        str(second.id),
    ]


async def test_a_category_without_children_carries_an_empty_list(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """So the client can render it as a plain option without a null check."""
    category = await make_category(db_session, "DevOps")

    branch = find((await api_client.get(CATEGORIES)).json(), category)

    assert branch is not None
    assert branch["children"] == []
