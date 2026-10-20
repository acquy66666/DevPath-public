"""The admin's money pages: revenue over time, by instructor, and the rankings.

Every sale here is dated in 2023 -- before anything the dev seed writes -- so a
platform-wide figure means the same on a laptop full of demo data as on an
empty CI database.

What is pinned down:

* **paid** is what buyers paid (`unit_price - discount`); the **instructor's
  share** is `floor(paid x frozen rate)`; the platform keeps the rest -- to
  the đồng, never rounded in the instructor's favour;
* a bucket is Vietnamese wall-clock time, at every size from hour to year,
  and a sale at 00:10 belongs to the new day;
* the previous range is the one of the same length just before;
* rankings tie like a race (1, 2, 2, 4) and carry the previous value;
* every page exports, and the export says what the screen says.
"""

from datetime import date, datetime, time
from decimal import Decimal
from io import BytesIO

import pytest
from httpx import AsyncClient
from openpyxl import load_workbook
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.services import finance
from app.services.vnpay import VIETNAM
from tests.api.test_commerce import make_course, make_user, sign_in
from tests.api.test_instructor_stats import sell

REVENUE = "/api/v1/admin/finance/revenue"
BREAKDOWN = "/api/v1/admin/finance/revenue/breakdown"
RANKINGS = "/api/v1/admin/finance/rankings"


def at(day: date, hour: int = 12, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute), VIETNAM)


@pytest.fixture
async def admin(db_session: AsyncSession) -> User:
    return await make_user(db_session, "admin")


@pytest.fixture
async def headers(api_client: AsyncClient, admin: User) -> dict[str, str]:
    return await sign_in(api_client, admin)


async def revenue(client: AsyncClient, headers: dict[str, str], **params) -> dict:
    response = await client.get(REVENUE, params=params, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def bucket(body: dict, prefix: str) -> dict:
    return next(p for p in body["series"] if p["bucket"].startswith(prefix))


# --- What a sale is worth ----------------------------------------------------------


def test_the_instructor_share_is_rounded_down_to_the_dong() -> None:
    """33 333 đ at 55 %: 18 333,15 đ owed, 18 333 đ paid; the 0,15 đ is the
    platform's. Rounding up would pay out money nobody took in."""
    assert finance.share_of(Decimal("33333.00"), Decimal("0.5500")) == Decimal("18333.00")
    assert finance.share_of(Decimal("199000.00"), Decimal("0.5000")) == Decimal("99500.00")


async def test_paid_share_and_platform_for_a_day(
    api_client: AsyncClient, db_session: AsyncSession, headers: dict[str, str]
) -> None:
    """One order, two instructors at two rates, a coupon on one line."""
    teacher = await make_user(db_session, "instructor")
    other = await make_user(db_session, "instructor")
    mine = await make_course(db_session, teacher, price="400000")
    theirs = await make_course(db_session, other, price="300000")
    buyer = await make_user(db_session)
    day = date(2023, 3, 15)
    await sell(
        db_session,
        buyer,
        [(mine, "400000", "120000"), (theirs, "300000", "0")],
        paid_at=at(day),
        share_rate="0.6000",
    )
    # Unpaid orders are not money.
    await sell(db_session, buyer, [(mine, "400000", "0")], paid_at=None, status="pending")

    body = await revenue(api_client, headers, start="2023-03-15", end="2023-03-15")

    assert body["totals"] == {
        "orders": 1,
        "lines": 2,
        "buyers": 1,
        "list_amount": "700000.00",
        "discount": "120000.00",
        "paid": "580000.00",
        "instructor_share": "348000.00",
        "platform_share": "232000.00",
    }

    only_mine = await revenue(
        api_client, headers, start="2023-03-15", end="2023-03-15", instructor_id=str(teacher.id)
    )
    assert only_mine["instructor"]["id"] == str(teacher.id)
    assert only_mine["totals"]["paid"] == "280000.00"
    assert only_mine["totals"]["instructor_share"] == "168000.00"


async def test_a_sale_just_after_midnight_belongs_to_the_new_day_and_hour(
    api_client: AsyncClient, db_session: AsyncSession, headers: dict[str, str]
) -> None:
    course = await make_course(db_session, await make_user(db_session, "instructor"))
    await sell(
        db_session,
        await make_user(db_session),
        [(course, "199000", "0")],
        paid_at=at(date(2023, 3, 16), 0, 10),
    )

    daily = await revenue(api_client, headers, start="2023-03-15", end="2023-03-16")
    hourly = await revenue(
        api_client, headers, start="2023-03-16", end="2023-03-16", granularity="hour"
    )

    assert bucket(daily, "2023-03-16")["paid"] == "199000.00"
    assert bucket(daily, "2023-03-15")["paid"] == "0.00"
    assert len(hourly["series"]) == 24
    assert bucket(hourly, "2023-03-16T00:00")["paid"] == "199000.00"
    assert bucket(hourly, "2023-03-16T01:00")["paid"] == "0.00"


@pytest.mark.parametrize(
    ("granularity", "start", "end", "buckets", "where"),
    [
        # 2023-03-15 is a Wednesday: its ISO week starts on Monday the 13th.
        ("week", "2023-03-01", "2023-03-31", 5, "2023-03-13"),
        ("month", "2023-01-01", "2023-12-31", 12, "2023-03-01"),
        ("quarter", "2023-01-01", "2023-12-31", 4, "2023-01-01"),
        ("year", "2022-01-01", "2023-12-31", 2, "2023-01-01"),
    ],
)
async def test_every_bucket_size_lines_up_with_the_calendar(
    api_client: AsyncClient,
    db_session: AsyncSession,
    headers: dict[str, str],
    granularity: str,
    start: str,
    end: str,
    buckets: int,
    where: str,
) -> None:
    course = await make_course(db_session, await make_user(db_session, "instructor"))
    await sell(
        db_session,
        await make_user(db_session),
        [(course, "199000", "0")],
        paid_at=at(date(2023, 3, 15)),
    )

    body = await revenue(api_client, headers, start=start, end=end, granularity=granularity)

    assert len(body["series"]) == buckets
    assert bucket(body, where)["paid"] == "199000.00"
    assert sum(Decimal(p["paid"]) for p in body["series"]) == Decimal("199000.00")


async def test_the_previous_range_is_the_one_just_before(
    api_client: AsyncClient, db_session: AsyncSession, headers: dict[str, str]
) -> None:
    course = await make_course(db_session, await make_user(db_session, "instructor"))
    buyer = await make_user(db_session)
    await sell(db_session, buyer, [(course, "100000", "0")], paid_at=at(date(2023, 3, 5)))
    await sell(db_session, buyer, [(course, "100000", "0")], paid_at=at(date(2023, 3, 12)))

    body = await revenue(api_client, headers, start="2023-03-10", end="2023-03-16")

    assert (body["previous_start"], body["previous_end"]) == ("2023-03-03", "2023-03-09")
    assert body["totals"]["paid"] == "100000.00"
    assert body["previous"]["paid"] == "100000.00"


@pytest.mark.parametrize(
    "params",
    [
        {"start": "2023-03-10", "end": "2023-03-01"},
        {"start": "2023-03-01", "end": "2023-03-20", "granularity": "hour"},
        {"start": "2023-03-01", "end": "2023-03-02", "granularity": "minute"},
    ],
)
async def test_a_range_that_makes_no_chart_is_refused(
    api_client: AsyncClient, headers: dict[str, str], params: dict
) -> None:
    response = await api_client.get(REVENUE, params=params, headers=headers)

    assert response.status_code == 422


async def test_the_breakdown_is_by_instructor_and_by_course(
    api_client: AsyncClient, db_session: AsyncSession, headers: dict[str, str]
) -> None:
    big = await make_user(db_session, "instructor")
    small = await make_user(db_session, "instructor")
    big_course = await make_course(db_session, big, title="Khóa lớn")
    small_course = await make_course(db_session, small, title="Khóa nhỏ")
    buyer = await make_user(db_session)
    day = at(date(2023, 3, 15))
    await sell(db_session, buyer, [(big_course, "300000", "0")], paid_at=day)
    await sell(db_session, buyer, [(small_course, "100000", "0")], paid_at=day)

    response = await api_client.get(
        BREAKDOWN, params={"start": "2023-03-15", "end": "2023-03-15"}, headers=headers
    )

    body = response.json()
    assert [row["instructor"]["id"] for row in body["instructors"]] == [str(big.id), str(small.id)]
    assert body["instructors"][0]["share_of_paid"] == 0.75
    assert body["instructors"][0]["tier"]["code"] == "khoi-hanh"
    assert [row["course_title"] for row in body["courses"]] == ["Khóa lớn", "Khóa nhỏ"]


async def test_the_revenue_export_holds_every_line(
    api_client: AsyncClient, db_session: AsyncSession, headers: dict[str, str]
) -> None:
    teacher = await make_user(db_session, "instructor")
    course = await make_course(db_session, teacher, title="=1+1")
    order = await sell(
        db_session,
        await make_user(db_session),
        [(course, "199000", "19900")],
        paid_at=at(date(2023, 3, 15)),
    )

    response = await api_client.get(
        f"{REVENUE}/export.xlsx",
        params={"start": "2023-03-15", "end": "2023-03-15"},
        headers=headers,
    )

    assert response.status_code == 200
    assert "devpath_doanh-thu_20230315_20230315.xlsx" in response.headers["content-disposition"]
    book = load_workbook(BytesIO(response.content))
    assert book.sheetnames == [
        "Tóm tắt",
        "Theo mốc",
        "Theo giảng viên",
        "Theo khóa học",
        "Dòng bán",
        "Định nghĩa",
    ]
    lines = [row for row in book["Dòng bán"].iter_rows(values_only=True) if row[0] == order.code]
    [line] = lines
    assert line[2] == "=1+1"  # a title, kept as text
    assert line[6:12] == (199000, 19900, 179100, 0.5, 89550, 89550)


# --- Rankings ------------------------------------------------------------------------


async def test_rankings_tie_like_a_race_and_carry_the_range_before(
    api_client: AsyncClient, db_session: AsyncSession, headers: dict[str, str]
) -> None:
    a, b, c = [await make_user(db_session, "instructor") for _ in range(3)]
    courses = {who: await make_course(db_session, who) for who in (a, b, c)}
    buyer = await make_user(db_session)
    day = at(date(2023, 3, 15))
    await sell(db_session, buyer, [(courses[a], "300000", "0")], paid_at=day)
    await sell(db_session, buyer, [(courses[b], "200000", "0")], paid_at=day)
    await sell(db_session, buyer, [(courses[c], "200000", "0")], paid_at=day)
    await sell(db_session, buyer, [(courses[c], "50000", "0")], paid_at=at(date(2023, 3, 1)))

    response = await api_client.get(
        RANKINGS, params={"start": "2023-03-10", "end": "2023-03-20"}, headers=headers
    )

    assert response.status_code == 200, response.text
    body = response.json()
    paid = next(r for r in body["rankings"] if r["code"] == "instructor_paid")
    assert [(e["rank"], e["key"]) for e in paid["entries"]][0] == (1, str(a.id))
    ranks = {e["key"]: e["rank"] for e in paid["entries"]}
    assert ranks[str(b.id)] == ranks[str(c.id)] == 2
    previous = {e["key"]: e["previous"] for e in paid["entries"]}
    assert Decimal(str(previous[str(c.id)])) == Decimal("50000")
    assert Decimal(str(previous[str(a.id)])) == 0
    assert body["concentration"]["top1"] == round(300000 / 700000, 4)
    assert {r["group"] for r in body["rankings"]} == {
        "instructors",
        "courses",
        "coupons",
        "categories",
    }


async def test_the_rankings_export_has_a_sheet_per_ranking(
    api_client: AsyncClient, headers: dict[str, str]
) -> None:
    response = await api_client.get(
        f"{RANKINGS}/export.xlsx",
        params={"start": "2023-03-10", "end": "2023-03-20"},
        headers=headers,
    )

    book = load_workbook(BytesIO(response.content))
    assert book.sheetnames[0] == "Tóm tắt"
    assert "Doanh thu theo giảng viên" in book.sheetnames
    assert len(book.sheetnames) == 1 + 17


async def test_the_overview_page_exports_too(
    api_client: AsyncClient, headers: dict[str, str]
) -> None:
    response = await api_client.get(
        "/api/v1/admin/stats/export.xlsx", params={"period": "7d"}, headers=headers
    )

    assert response.status_code == 200
    book = load_workbook(BytesIO(response.content))
    assert book.sheetnames == ["Tổng quan", "Theo thời gian", "Khóa học hot"]
