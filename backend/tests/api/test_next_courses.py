"""`GET /api/v1/courses/{course_id}/next` over HTTP -- "Học tiếp theo".

The block a reader sees after finishing a course: its nearest neighbours, less
the ones this reader already has. The ranking is `/similar`'s and is proved in
`tests/test_content_based.py`; the leaving-out is proved there too, including
that it happens before the `LIMIT`. What this file checks is the contract: the
same cards as `/similar`, sign-in required because the answer depends on whose
history it is, and the same 404 for a course the public cannot see.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Course, Enrollment
from tests.api import test_similar_courses as similar
from tests.api.test_recommendations import make_user, sign_in

#: The same three courses `/similar` is tested on -- viewed, near, far.
catalogue = similar.catalogue
embed = similar.embed


def url(course: Course | uuid.UUID) -> str:
    course_id = course if isinstance(course, uuid.UUID) else course.id
    return f"/api/v1/courses/{course_id}/next"


async def test_the_next_block_leaves_out_what_the_reader_already_has(
    api_client: AsyncClient, db_session: AsyncSession, catalogue: dict[str, Course]
) -> None:
    await embed(db_session, catalogue)
    reader = await make_user(db_session, "student")
    db_session.add_all(
        Enrollment(user_id=reader.id, course_id=catalogue[key].id)
        for key in ("viewed", "near")
    )
    await db_session.flush()

    response = await api_client.get(
        url(catalogue["viewed"]), headers=await sign_in(api_client, reader)
    )

    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert [item["id"] for item in items] == [str(catalogue["far"].id)]
    assert items[0]["title"] == "Thiết kế đồ họa"
    assert items[0]["instructor"]["full_name"] == "Giảng viên"
    assert "score" in items[0]


async def test_a_reader_with_nothing_yet_gets_the_same_order_as_similar(
    api_client: AsyncClient, db_session: AsyncSession, catalogue: dict[str, Course]
) -> None:
    await embed(db_session, catalogue)
    reader = await make_user(db_session, "student")

    response = await api_client.get(
        url(catalogue["viewed"]), headers=await sign_in(api_client, reader)
    )

    assert [item["id"] for item in response.json()["items"]] == [
        str(catalogue["near"].id),
        str(catalogue["far"].id),
    ]


async def test_the_next_block_needs_a_signed_in_reader(
    api_client: AsyncClient, catalogue: dict[str, Course]
) -> None:
    """The answer depends on whose history it is, so there is no anonymous one."""
    response = await api_client.get(url(catalogue["viewed"]))

    assert response.status_code == 401


async def test_a_draft_course_is_a_404(
    api_client: AsyncClient, db_session: AsyncSession, catalogue: dict[str, Course]
) -> None:
    reader = await make_user(db_session, "student")
    catalogue["viewed"].status = "draft"
    await db_session.flush()

    response = await api_client.get(
        url(catalogue["viewed"]), headers=await sign_in(api_client, reader)
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "COURSE_NOT_FOUND"


async def test_an_unknown_course_is_a_404(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    reader = await make_user(db_session, "student")

    response = await api_client.get(
        url(uuid.uuid4()), headers=await sign_in(api_client, reader)
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "COURSE_NOT_FOUND"


@pytest.mark.parametrize("limit", [0, 100])
async def test_an_impossible_limit_is_refused(
    api_client: AsyncClient,
    db_session: AsyncSession,
    catalogue: dict[str, Course],
    limit: int,
) -> None:
    reader = await make_user(db_session, "student")

    response = await api_client.get(
        url(catalogue["viewed"]),
        params={"limit": limit},
        headers=await sign_in(api_client, reader),
    )

    assert response.status_code == 422
