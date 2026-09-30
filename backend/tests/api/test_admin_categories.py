"""The admin curating the category tree.

What must hold: two levels and no more; no two siblings share a name; the
slug is made once and survives a rename; an order is a whole level at once;
and nothing in use -- by a course, even a taken-down one, or by a child
category -- can be deleted out from under it.

Names carry a token: the dev database already holds the seeded taxonomy.
"""

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category, Course
from tests.api.publishing import admin_headers
from tests.api.test_commerce import make_user, sign_in

URL = "/api/v1/admin/categories"


@pytest.fixture
async def admin(api_client: AsyncClient, db_session: AsyncSession) -> dict[str, str]:
    return await admin_headers(api_client, db_session)


@pytest.fixture
def token() -> str:
    return uuid.uuid4().hex[:8]


async def create(client: AsyncClient, headers: dict, name: str, parent_id=None) -> dict:
    response = await client.post(URL, json={"name": name, "parent_id": parent_id}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def find(tree: list[dict], category_id: str) -> dict:
    for parent in tree:
        if parent["id"] == category_id:
            return parent
        for child in parent["children"]:
            if child["id"] == category_id:
                return child
    raise AssertionError(f"{category_id} not in tree")


async def test_only_an_admin_curates(
    api_client: AsyncClient, db_session: AsyncSession, token: str
) -> None:
    assert (await api_client.post(URL, json={"name": token})).status_code == 401
    teacher = await make_user(db_session, "instructor")
    response = await api_client.post(
        URL, json={"name": token}, headers=await sign_in(api_client, teacher)
    )
    assert response.status_code == 403


async def test_a_category_gets_a_clean_slug_and_goes_last(
    api_client: AsyncClient, admin: dict, token: str
) -> None:
    parent = await create(api_client, admin, f"Dữ liệu {token}")
    first = await create(api_client, admin, f"Phân tích {token}", parent["id"])
    second = await create(api_client, admin, f"Trực quan {token}", parent["id"])

    assert parent["slug"] == f"du-lieu-{token}"
    assert parent["parent_id"] is None
    assert first["parent_id"] == parent["id"]
    assert (first["position"], second["position"]) == (0, 1)

    # Visible to everybody at once: the public tree is the same rows.
    public = (await api_client.get("/api/v1/categories")).json()
    assert [c["name"] for c in find(public, parent["id"])["children"]] == [
        f"Phân tích {token}",
        f"Trực quan {token}",
    ]


async def test_a_taken_slug_gets_a_suffix(
    api_client: AsyncClient, admin: dict, token: str
) -> None:
    first = await create(api_client, admin, f"Mạng {token}")
    parent = await create(api_client, admin, f"Hệ thống {token}")
    # Same words under another parent: allowed, but the slug is global.
    second = await create(api_client, admin, f"Mạng {token}", parent["id"])

    assert first["slug"] == f"mang-{token}"
    assert second["slug"].startswith(f"mang-{token}-")


async def test_two_levels_and_no_more(api_client: AsyncClient, admin: dict, token: str) -> None:
    parent = await create(api_client, admin, f"Cha {token}")
    child = await create(api_client, admin, f"Con {token}", parent["id"])

    grandchild = await api_client.post(
        URL, json={"name": f"Cháu {token}", "parent_id": child["id"]}, headers=admin
    )
    unknown = await api_client.post(
        URL, json={"name": f"Mồ côi {token}", "parent_id": str(uuid.uuid4())}, headers=admin
    )

    assert grandchild.status_code == 409
    assert grandchild.json()["detail"]["code"] == "CATEGORY_TOO_DEEP"
    assert unknown.status_code == 404


async def test_siblings_do_not_share_a_name(
    api_client: AsyncClient, admin: dict, token: str
) -> None:
    await create(api_client, admin, f"Trùng {token}")

    response = await api_client.post(URL, json={"name": f"  TRÙNG {token}  "}, headers=admin)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "CATEGORY_NAME_TAKEN"


async def test_renaming_keeps_the_slug_and_moving_goes_last(
    api_client: AsyncClient, admin: dict, token: str
) -> None:
    left = await create(api_client, admin, f"Trái {token}")
    right = await create(api_client, admin, f"Phải {token}")
    await create(api_client, admin, f"Đã có {token}", right["id"])
    moving = await create(api_client, admin, f"Di chuyển {token}", left["id"])

    response = await api_client.patch(
        f"{URL}/{moving['id']}",
        json={"name": f"Đã đổi tên {token}", "parent_id": right["id"]},
        headers=admin,
    )
    to_top = await api_client.patch(
        f"{URL}/{moving['id']}", json={"parent_id": None}, headers=admin
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["name"] == f"Đã đổi tên {token}"
    assert body["slug"] == moving["slug"]
    assert body["parent_id"] == right["id"]
    assert body["position"] == 1
    assert to_top.json()["parent_id"] is None


async def test_a_parent_cannot_move_under_another_or_itself(
    api_client: AsyncClient, admin: dict, token: str
) -> None:
    parent = await create(api_client, admin, f"Có con {token}")
    await create(api_client, admin, f"Đứa con {token}", parent["id"])
    other = await create(api_client, admin, f"Khác {token}")

    under_other = await api_client.patch(
        f"{URL}/{parent['id']}", json={"parent_id": other["id"]}, headers=admin
    )
    under_itself = await api_client.patch(
        f"{URL}/{other['id']}", json={"parent_id": other["id"]}, headers=admin
    )

    assert under_other.status_code == 409
    assert under_itself.status_code == 409


async def test_an_order_is_a_whole_level(api_client: AsyncClient, admin: dict, token: str) -> None:
    parent = await create(api_client, admin, f"Sắp xếp {token}")
    a = await create(api_client, admin, f"A {token}", parent["id"])
    b = await create(api_client, admin, f"B {token}", parent["id"])
    c = await create(api_client, admin, f"C {token}", parent["id"])

    response = await api_client.put(
        f"{URL}/order",
        json={"parent_id": parent["id"], "ids": [c["id"], a["id"], b["id"]]},
        headers=admin,
    )
    partial = await api_client.put(
        f"{URL}/order", json={"parent_id": parent["id"], "ids": [a["id"], b["id"]]}, headers=admin
    )

    assert response.status_code == 200
    children = find(response.json(), parent["id"])["children"]
    assert [child["id"] for child in children] == [c["id"], a["id"], b["id"]]
    assert partial.status_code == 400
    assert partial.json()["detail"]["code"] == "INVALID_ORDER"


async def test_nothing_in_use_can_be_deleted(
    api_client: AsyncClient, db_session: AsyncSession, admin: dict, token: str
) -> None:
    parent = await create(api_client, admin, f"Bận {token}")
    child = await create(api_client, admin, f"Đang dùng {token}", parent["id"])
    teacher = await make_user(db_session, "instructor")
    # Taken down, but still a row the foreign key protects.
    db_session.add(
        Course(
            instructor_id=teacher.id,
            category_id=uuid.UUID(child["id"]),
            title="Khóa đã gỡ",
            slug=f"khoa-da-go-{token}",
            status="draft",
            deleted_at=datetime.now(UTC),
        )
    )
    await db_session.flush()

    with_children = await api_client.delete(f"{URL}/{parent['id']}", headers=admin)
    with_course = await api_client.delete(f"{URL}/{child['id']}", headers=admin)

    assert with_children.status_code == 409
    assert with_children.json()["detail"]["code"] == "CATEGORY_HAS_CHILDREN"
    assert with_course.status_code == 409
    assert with_course.json()["detail"]["code"] == "CATEGORY_IN_USE"
    # The listing counts live courses only.
    tree = (await api_client.get(URL, headers=admin)).json()
    assert find(tree, child["id"])["courses_count"] == 0


async def test_an_empty_category_is_deleted(
    api_client: AsyncClient, db_session: AsyncSession, admin: dict, token: str
) -> None:
    empty = await create(api_client, admin, f"Trống {token}")

    response = await api_client.delete(f"{URL}/{empty['id']}", headers=admin)
    again = await api_client.delete(f"{URL}/{empty['id']}", headers=admin)

    assert response.status_code == 204
    assert await db_session.get(Category, uuid.UUID(empty["id"])) is None
    assert again.status_code == 404
