"""The admin's discount campaigns.

What must hold: a code is made once, in upper case, and never changes; the
table's rules come back as 422s with a sentence rather than 500s; status is
worked out from the dates and the count; the limit never drops below what was
used; ending early is `valid_to = now`; and a code somebody used is never
deleted. Codes carry a token: the dev database has the seeded campaigns.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Coupon
from app.services import coupons as coupons_service
from tests.api.publishing import admin_headers
from tests.api.test_commerce import make_course, make_user, sign_in

URL = "/api/v1/admin/coupons"


@pytest.fixture
async def admin(api_client: AsyncClient, db_session: AsyncSession) -> dict[str, str]:
    return await admin_headers(api_client, db_session)


@pytest.fixture
def code() -> str:
    return f"T{uuid.uuid4().hex[:8].upper()}"


def iso(moment: datetime) -> str:
    return moment.isoformat()


async def create(client: AsyncClient, headers: dict, **body) -> dict:
    response = await client.post(URL, json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def test_only_an_admin_runs_campaigns(
    api_client: AsyncClient, db_session: AsyncSession, code: str
) -> None:
    body = {"code": code, "discount_type": "percent", "value": "10"}
    assert (await api_client.post(URL, json=body)).status_code == 401
    teacher = await make_user(db_session, "instructor")
    response = await api_client.post(URL, json=body, headers=await sign_in(api_client, teacher))
    assert response.status_code == 403


async def test_a_site_wide_code_is_live_at_once_and_usable_at_checkout(
    api_client: AsyncClient, db_session: AsyncSession, admin: dict, code: str
) -> None:
    body = await create(
        api_client, admin, code=f"  {code.lower()} ", discount_type="percent", value="20"
    )

    assert body["code"] == code
    assert body["status"] == "live"
    assert body["scope"] == "site"
    assert body["used_count"] == 0
    # The checkout's own lookup finds it and finds it live.
    coupon = await coupons_service.find_coupon(db_session, code.lower())
    coupons_service.assert_live(coupon)


async def test_a_code_is_one_campaign(api_client: AsyncClient, admin: dict, code: str) -> None:
    await create(api_client, admin, code=code, discount_type="fixed", value="50000")

    again = await api_client.post(
        URL, json={"code": code.lower(), "discount_type": "percent", "value": "5"}, headers=admin
    )

    assert again.status_code == 409
    assert again.json()["detail"]["code"] == "COUPON_CODE_TAKEN"


@pytest.mark.parametrize(
    "body",
    [
        {"code": "GIẢM 50", "discount_type": "percent", "value": "50"},
        {"code": "AB", "discount_type": "percent", "value": "50"},
        {"code": "{code}", "discount_type": "percent", "value": "150"},
        {"code": "{code}", "discount_type": "fixed", "value": "0"},
        {"code": "{code}", "discount_type": "percent", "value": "10", "scope": "courses"},
        {
            "code": "{code}",
            "discount_type": "percent",
            "value": "10",
            "valid_from": "2031-06-10T00:00:00+07:00",
            "valid_to": "2031-06-01T00:00:00+07:00",
        },
        {"code": "{code}", "discount_type": "percent", "value": "10", "max_uses": 0},
    ],
)
async def test_a_code_the_table_would_refuse_is_a_422(
    api_client: AsyncClient, admin: dict, code: str, body: dict
) -> None:
    payload = {key: (code if value == "{code}" else value) for key, value in body.items()}
    response = await api_client.post(URL, json=payload, headers=admin)
    assert response.status_code == 422, response.text


async def test_a_code_limited_to_courses_names_them(
    api_client: AsyncClient, db_session: AsyncSession, admin: dict, code: str
) -> None:
    teacher = await make_user(db_session, "instructor")
    python = await make_course(db_session, teacher, title="Python cơ bản")
    web = await make_course(db_session, teacher, title="HTML và CSS")

    body = await create(
        api_client,
        admin,
        code=code,
        discount_type="percent",
        value="30",
        scope="courses",
        course_ids=[str(python.id), str(web.id)],
    )
    unknown = await api_client.post(
        URL,
        json={
            "code": f"{code}X",
            "discount_type": "percent",
            "value": "30",
            "scope": "courses",
            "course_ids": [str(uuid.uuid4())],
        },
        headers=admin,
    )

    assert [course["title"] for course in body["courses"]] == ["HTML và CSS", "Python cơ bản"]
    coupon = await coupons_service.find_coupon(db_session, code)
    assert await coupons_service.covered_course_ids(db_session, coupon) == {python.id, web.id}
    assert unknown.status_code == 404

    # Widening it to the whole site drops the list.
    widened = await api_client.patch(f"{URL}/{body['id']}", json={"scope": "site"}, headers=admin)
    assert widened.json()["courses"] == []


async def test_status_comes_from_the_dates_and_the_count(
    api_client: AsyncClient, db_session: AsyncSession, admin: dict, code: str
) -> None:
    now = datetime.now(UTC)
    scheduled = await create(
        api_client,
        admin,
        code=f"{code}S",
        discount_type="percent",
        value="10",
        valid_from=iso(now + timedelta(days=3)),
    )
    exhausted = await create(
        api_client, admin, code=f"{code}X", discount_type="percent", value="10", max_uses=1
    )
    row = await db_session.get(Coupon, uuid.UUID(exhausted["id"]))
    row.used_count = 1
    ended = await create(
        api_client,
        admin,
        code=f"{code}E",
        discount_type="percent",
        value="10",
        valid_from=iso(now - timedelta(days=10)),
        valid_to=iso(now - timedelta(days=1)),
    )
    await db_session.flush()

    listed = (await api_client.get(URL, params={"q": code}, headers=admin)).json()["items"]
    by_code = {item["code"]: item["status"] for item in listed}
    only_ended = (
        await api_client.get(URL, params={"q": code, "status": "ended"}, headers=admin)
    ).json()

    assert by_code == {
        scheduled["code"]: "scheduled",
        exhausted["code"]: "exhausted",
        ended["code"]: "ended",
    }
    assert [item["code"] for item in only_ended["items"]] == [ended["code"]]


async def test_the_limit_never_drops_below_what_was_used(
    api_client: AsyncClient, db_session: AsyncSession, admin: dict, code: str
) -> None:
    body = await create(
        api_client, admin, code=code, discount_type="fixed", value="100000", max_uses=10
    )
    row = await db_session.get(Coupon, uuid.UUID(body["id"]))
    row.used_count = 4
    await db_session.flush()

    too_low = await api_client.patch(f"{URL}/{body['id']}", json={"max_uses": 3}, headers=admin)
    fine = await api_client.patch(
        f"{URL}/{body['id']}", json={"max_uses": 4, "value": "120000"}, headers=admin
    )
    unlimited = await api_client.patch(
        f"{URL}/{body['id']}", json={"max_uses": None}, headers=admin
    )
    to_percent = await api_client.patch(
        f"{URL}/{body['id']}", json={"discount_type": "percent"}, headers=admin
    )

    assert too_low.status_code == 409
    assert too_low.json()["detail"]["code"] == "COUPON_LIMIT_BELOW_USED"
    assert fine.status_code == 200
    assert fine.json()["value"] == "120000.00"
    assert fine.json()["status"] == "exhausted"
    assert unlimited.json()["max_uses"] is None
    # 120.000 as a percentage would be 120.000 %.
    assert to_percent.status_code == 422
    assert to_percent.json()["detail"]["code"] == "INVALID_COUPON_VALUE"


async def test_ending_early_sets_the_end_to_now(
    api_client: AsyncClient, admin: dict, code: str
) -> None:
    live = await create(api_client, admin, code=code, discount_type="percent", value="10")
    later = await create(
        api_client,
        admin,
        code=f"{code}L",
        discount_type="percent",
        value="10",
        valid_from=iso(datetime.now(UTC) + timedelta(days=2)),
    )

    ended = await api_client.post(f"{URL}/{live['id']}/end", headers=admin)
    again = await api_client.post(f"{URL}/{live['id']}/end", headers=admin)
    not_started = await api_client.post(f"{URL}/{later['id']}/end", headers=admin)

    assert ended.status_code == 200
    assert ended.json()["status"] == "ended"
    assert ended.json()["valid_to"] is not None
    assert again.json()["valid_to"] == ended.json()["valid_to"]
    assert not_started.status_code == 409
    assert not_started.json()["detail"]["code"] == "COUPON_NOT_STARTED"


async def test_only_an_unused_code_is_deleted(
    api_client: AsyncClient, db_session: AsyncSession, admin: dict, code: str
) -> None:
    unused = await create(api_client, admin, code=code, discount_type="percent", value="10")
    used = await create(api_client, admin, code=f"{code}U", discount_type="percent", value="10")
    row = await db_session.get(Coupon, uuid.UUID(used["id"]))
    row.used_count = 1
    await db_session.flush()

    gone = await api_client.delete(f"{URL}/{unused['id']}", headers=admin)
    kept = await api_client.delete(f"{URL}/{used['id']}", headers=admin)
    missing = await api_client.delete(f"{URL}/{unused['id']}", headers=admin)

    assert gone.status_code == 204
    assert kept.status_code == 409
    assert kept.json()["detail"]["code"] == "COUPON_IN_USE"
    assert missing.status_code == 404
