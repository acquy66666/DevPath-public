"""The profit page and the expenses behind it.

Sales and expenses are dated in 2023, before any demo data, so the year's
columns hold exactly what each test wrote.
"""

from datetime import date, datetime, time
from decimal import Decimal
from io import BytesIO

import pytest
from httpx import AsyncClient
from openpyxl import load_workbook
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import profit
from app.services.vnpay import VIETNAM
from tests.api.test_commerce import make_course, make_user, sign_in
from tests.api.test_instructor_stats import sell

PROFIT = "/api/v1/admin/finance/profit"
EXPENSES = "/api/v1/admin/expenses"


def at(day: date) -> datetime:
    return datetime.combine(day, time(12), VIETNAM)


@pytest.fixture
async def headers(api_client: AsyncClient, db_session: AsyncSession) -> dict[str, str]:
    return await sign_in(api_client, await make_user(db_session, "admin"))


async def spend(
    client: AsyncClient, headers: dict[str, str], day: str, category: str, amount: str
) -> dict:
    response = await client.post(
        EXPENSES,
        json={"incurred_on": day, "category": category, "description": "Hóa đơn", "amount": amount},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_the_profit_and_loss_adds_up(
    api_client: AsyncClient, db_session: AsyncSession, headers: dict[str, str]
) -> None:
    """March 2023: one 500 000 đ sale with a 100 000 đ coupon through VNPay,
    one free checkout. 400 000 đ collected, 200 000 đ to the instructor, a
    3 200 đ gateway fee on the paid order only, 150 000 đ of servers and
    20 000 đ of tax."""
    teacher = await make_user(db_session, "instructor")
    course = await make_course(db_session, teacher)
    buyer = await make_user(db_session)
    await sell(db_session, buyer, [(course, "500000", "100000")], paid_at=at(date(2023, 3, 10)))
    await sell(
        db_session,
        buyer,
        [(course, "500000", "500000")],
        paid_at=at(date(2023, 3, 11)),
        provider="none",
    )
    await spend(api_client, headers, "2023-03-31", "infrastructure", "150000")
    await spend(api_client, headers, "2023-03-31", "tax", "20000")

    response = await api_client.get(PROFIT, params={"year": 2023}, headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["columns"]) == 12
    march = body["columns"][2]
    assert (march["start"], march["end"]) == ("2023-03-01", "2023-03-31")
    assert march["list_amount"] == "1000000.00"
    assert march["discount"] == "600000.00"
    assert march["collected"] == "400000.00"
    assert march["instructor_share"] == "200000.00"
    assert march["platform_revenue"] == "200000.00"
    assert march["gateway_orders"] == 1
    assert march["gateway_fee"] == "3200.00"
    assert march["expenses"]["infrastructure"] == "150000.00"
    assert march["operating_expenses"] == "150000.00"
    assert march["profit_before_tax"] == "46800.00"
    assert march["tax"] == "20000.00"
    assert march["retained"] == "26800.00"
    assert march["take_rate"] == 0.2
    assert body["total"]["retained"] == "26800.00"
    assert body["fee_rate"] == "0.008"


async def test_quarters_and_the_export(
    api_client: AsyncClient, db_session: AsyncSession, headers: dict[str, str]
) -> None:
    await spend(api_client, headers, "2023-05-02", "marketing", "90000")

    quarters = await api_client.get(
        PROFIT, params={"year": 2023, "granularity": "quarter"}, headers=headers
    )
    export = await api_client.get(f"{PROFIT}/export.xlsx", params={"year": 2023}, headers=headers)

    assert [c["start"] for c in quarters.json()["columns"]] == [
        "2023-01-01",
        "2023-04-01",
        "2023-07-01",
        "2023-10-01",
    ]
    assert quarters.json()["columns"][1]["expenses"]["marketing"] == "90000.00"
    book = load_workbook(BytesIO(export.content))
    assert book.sheetnames == ["Lãi lỗ", "Tỉ suất", "Chi phí", "Giả định"]
    rows = {row[0]: row for row in book["Lãi lỗ"].iter_rows(values_only=True) if row[0]}
    assert rows["− Marketing"][5] == 90000  # May is the fifth month column


def test_the_gateway_fee_is_rounded_to_the_dong() -> None:
    assert profit.gateway_fee(Decimal("199000.00")) == Decimal("1592.00")
    assert profit.gateway_fee(Decimal("187.00")) == Decimal("1.00")


async def test_expenses_are_listed_by_month_with_their_total(
    api_client: AsyncClient, headers: dict[str, str]
) -> None:
    await spend(api_client, headers, "2023-06-01", "ai_api", "120000")
    await spend(api_client, headers, "2023-06-20", "infrastructure", "80000")
    await spend(api_client, headers, "2023-07-01", "infrastructure", "80000")

    june = await api_client.get(EXPENSES, params={"year": 2023, "month": 6}, headers=headers)
    servers = await api_client.get(
        EXPENSES, params={"year": 2023, "category": "infrastructure"}, headers=headers
    )
    export = await api_client.get(
        f"{EXPENSES}/export.xlsx", params={"year": 2023, "month": 6}, headers=headers
    )

    assert june.json()["total"] == 2
    assert june.json()["amount"] == "200000.00"
    assert [e["incurred_on"] for e in june.json()["items"]] == ["2023-06-20", "2023-06-01"]
    assert servers.json()["amount"] == "160000.00"
    assert load_workbook(BytesIO(export.content)).sheetnames == ["Chi phí"]


@pytest.mark.parametrize(
    "body",
    [
        {"incurred_on": "2023-06-01", "category": "ai_api", "description": "x", "amount": "0"},
        {"incurred_on": "2023-06-01", "category": "ai_api", "description": "  ", "amount": "1"},
        {"incurred_on": "2023-06-01", "category": "lunch", "description": "x", "amount": "1"},
        {"incurred_on": "2023-06-01", "category": "ai_api", "description": "x", "amount": "1.001"},
    ],
)
async def test_an_expense_that_is_not_one_is_refused(
    api_client: AsyncClient, headers: dict[str, str], body: dict
) -> None:
    response = await api_client.post(EXPENSES, json=body, headers=headers)

    assert response.status_code == 422


async def test_an_expense_is_edited_and_deleted(
    api_client: AsyncClient, headers: dict[str, str]
) -> None:
    expense = await spend(api_client, headers, "2023-06-01", "other", "5000")
    url = f"{EXPENSES}/{expense['id']}"

    edited = await api_client.patch(
        url, json={"amount": "7000", "category": "staff"}, headers=headers
    )
    nulled = await api_client.patch(url, json={"amount": None}, headers=headers)
    empty = await api_client.patch(url, json={}, headers=headers)
    deleted = await api_client.delete(url, headers=headers)
    again = await api_client.delete(url, headers=headers)

    assert edited.status_code == 200
    assert (edited.json()["amount"], edited.json()["category"]) == ("7000.00", "staff")
    assert nulled.status_code == 422
    assert empty.status_code == 422
    assert deleted.status_code == 204
    assert again.status_code == 404
    assert again.json()["detail"]["code"] == "EXPENSE_NOT_FOUND"
