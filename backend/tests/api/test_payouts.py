"""Payout statements: each sale billed once, locked once confirmed, paid once.

All sales are in 2023 and every batch names its instructors, so the dev
database's demo sales never land on a statement drawn up here.
"""

from datetime import date, datetime, time
from decimal import Decimal
from io import BytesIO

import pytest
from httpx import AsyncClient
from openpyxl import load_workbook
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.services import payouts
from app.services.vnpay import VIETNAM
from tests.api.test_commerce import make_course, make_user, sign_in
from tests.api.test_instructor_stats import sell

STATEMENTS = "/api/v1/admin/payouts/statements"
BALANCES = "/api/v1/admin/payouts/balances"


def at(day: date, hour: int = 12) -> datetime:
    return datetime.combine(day, time(hour), VIETNAM)


@pytest.fixture
async def admin(db_session: AsyncSession) -> User:
    return await make_user(db_session, "admin")


@pytest.fixture
async def headers(api_client: AsyncClient, admin: User) -> dict[str, str]:
    return await sign_in(api_client, admin)


@pytest.fixture
async def teacher(db_session: AsyncSession) -> User:
    return await make_user(db_session, "instructor")


async def draw_up(
    client: AsyncClient, headers: dict[str, str], month: str, *instructors: User
) -> dict:
    response = await client.post(
        STATEMENTS,
        json={"month": month, "instructor_ids": [str(u.id) for u in instructors]},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


async def detail(client: AsyncClient, headers: dict[str, str], statement_id: str) -> dict:
    response = await client.get(f"{STATEMENTS}/{statement_id}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def test_a_month_that_is_not_over_cannot_be_billed(
    api_client: AsyncClient, headers: dict[str, str], teacher: User
) -> None:
    month = datetime.now(VIETNAM).date().replace(day=1).isoformat()

    response = await api_client.post(
        STATEMENTS, json={"month": month, "instructor_ids": [str(teacher.id)]}, headers=headers
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "PAYOUT_PERIOD_NOT_OVER"


async def test_a_statement_carries_unbilled_lines_in_and_stops_at_its_month(
    api_client: AsyncClient, db_session: AsyncSession, headers: dict[str, str], teacher: User
) -> None:
    """February was never billed: its sale is carried into March's statement.
    April's sale waits for April. A 0 đ line earns nothing and is not billed."""
    course = await make_course(db_session, teacher, title="Khóa A")
    buyer = await make_user(db_session)
    await sell(db_session, buyer, [(course, "333333", "0")], paid_at=at(date(2023, 2, 10)))
    await sell(db_session, buyer, [(course, "500000", "100000")], paid_at=at(date(2023, 3, 31), 23))
    await sell(
        db_session,
        buyer,
        [(course, "500000", "500000")],
        paid_at=at(date(2023, 3, 20)),
        provider="none",
    )
    await sell(db_session, buyer, [(course, "200000", "0")], paid_at=at(date(2023, 4, 1), 0))

    batch = await draw_up(api_client, headers, "2023-03-15", teacher)

    assert (batch["period_start"], batch["period_end"]) == ("2023-03-01", "2023-03-31")
    [created] = batch["created"]
    assert created["status"] == "draft"
    assert created["code"].startswith("BK2303")
    assert created["instructor_email"] == teacher.email
    assert created["line_count"] == 2
    assert created["gross_amount"] == "733333.00"
    # floor(333 333 x 0.5) + 400 000 x 0.5 = 166 666 + 200 000
    assert created["instructor_amount"] == "366666.00"
    assert created["platform_amount"] == "366667.00"
    assert created["tax_withheld"] == "0.00"
    assert created["payable_amount"] == "366666.00"

    body = await detail(api_client, headers, created["id"])
    assert body["carried_lines"] == 1
    paid_at = [line["paid_at"] for line in body["lines"]]
    assert paid_at == sorted(paid_at)
    assert {line["course_title"] for line in body["lines"]} == {"Khóa A"}


async def test_each_sale_is_billed_once(
    api_client: AsyncClient, db_session: AsyncSession, headers: dict[str, str], teacher: User
) -> None:
    course = await make_course(db_session, teacher)
    buyer = await make_user(db_session)
    await sell(db_session, buyer, [(course, "600000", "0")], paid_at=at(date(2023, 3, 10)))

    first = await draw_up(api_client, headers, "2023-03-01", teacher)
    again = await draw_up(api_client, headers, "2023-03-01", teacher)
    later = await draw_up(api_client, headers, "2023-05-01", teacher)

    assert len(first["created"]) == 1
    assert again["created"] == [] and again["skipped"] == []
    assert later["created"] == []


async def test_under_the_minimum_waits_except_in_december(
    api_client: AsyncClient, db_session: AsyncSession, headers: dict[str, str], teacher: User
) -> None:
    """A 199 000 đ sale earns 99 500 đ, under the 200 000 đ minimum: skipped
    in March and carried. December pays out whatever there is."""
    course = await make_course(db_session, teacher)
    await sell(
        db_session,
        await make_user(db_session),
        [(course, "199000", "0")],
        paid_at=at(date(2023, 3, 3)),
    )

    march = await draw_up(api_client, headers, "2023-03-01", teacher)
    december = await draw_up(api_client, headers, "2023-12-01", teacher)

    assert march["created"] == []
    assert march["skipped"][0]["amount"] == "99500.00"
    assert march["skipped"][0]["instructor"]["id"] == str(teacher.id)
    [paid_out] = december["created"]
    assert paid_out["instructor_amount"] == "99500.00"


async def test_tax_is_withheld_from_five_million_and_can_be_switched_off_on_a_draft(
    api_client: AsyncClient, db_session: AsyncSession, headers: dict[str, str], teacher: User
) -> None:
    course = await make_course(db_session, teacher)
    buyer = await make_user(db_session)
    await sell(db_session, buyer, [(course, "10000001", "0")], paid_at=at(date(2023, 3, 3)))

    [statement] = (await draw_up(api_client, headers, "2023-03-01", teacher))["created"]

    assert statement["instructor_amount"] == "5000000.00"
    assert statement["tax_withheld"] == "500000.00"
    assert statement["payable_amount"] == "4500000.00"

    response = await api_client.patch(
        f"{STATEMENTS}/{statement['id']}",
        json={"withhold": False, "note": "Đã nộp mẫu 08/CK-TNCN"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["tax_withheld"] == "0.00"
    assert response.json()["payable_amount"] == "5000000.00"
    assert response.json()["note"] == "Đã nộp mẫu 08/CK-TNCN"


async def test_a_statement_moves_draft_confirmed_paid_and_no_other_way(
    api_client: AsyncClient, db_session: AsyncSession, headers: dict[str, str], teacher: User
) -> None:
    course = await make_course(db_session, teacher)
    await sell(
        db_session,
        await make_user(db_session),
        [(course, "600000", "0")],
        paid_at=at(date(2023, 3, 3)),
    )
    [statement] = (await draw_up(api_client, headers, "2023-03-01", teacher))["created"]
    url = f"{STATEMENTS}/{statement['id']}"

    early_pay = await api_client.post(f"{url}/pay", json={"reference": "FT123"}, headers=headers)
    assert early_pay.status_code == 409

    confirmed = await api_client.post(f"{url}/confirm", headers=headers)
    assert confirmed.json()["status"] == "confirmed"
    assert confirmed.json()["confirmed_at"] is not None

    locked = await api_client.patch(url, json={"withhold": False}, headers=headers)
    assert locked.status_code == 409
    assert locked.json()["detail"]["code"] == "PAYOUT_STATEMENT_STATE"
    assert (await api_client.delete(url, headers=headers)).status_code == 409

    blank = await api_client.post(f"{url}/pay", json={"reference": "  "}, headers=headers)
    assert blank.status_code == 422
    paid = await api_client.post(f"{url}/pay", json={"reference": "FT26103999"}, headers=headers)
    assert paid.json()["status"] == "paid"
    assert paid.json()["payment_reference"] == "FT26103999"

    voided = await api_client.post(f"{url}/void", json={"reason": "Nhầm"}, headers=headers)
    assert voided.status_code == 409


async def test_voiding_frees_the_lines_and_keeps_the_header(
    api_client: AsyncClient, db_session: AsyncSession, headers: dict[str, str], teacher: User
) -> None:
    course = await make_course(db_session, teacher)
    await sell(
        db_session,
        await make_user(db_session),
        [(course, "600000", "0")],
        paid_at=at(date(2023, 3, 3)),
    )
    [statement] = (await draw_up(api_client, headers, "2023-03-01", teacher))["created"]
    url = f"{STATEMENTS}/{statement['id']}"
    await api_client.post(f"{url}/confirm", headers=headers)

    voided = await api_client.post(f"{url}/void", json={"reason": "Sai kỳ"}, headers=headers)

    assert voided.status_code == 200
    body = voided.json()
    assert body["status"] == "void" and body["void_reason"] == "Sai kỳ"
    assert body["lines"] == []
    assert body["instructor_amount"] == "300000.00"  # the header remembers
    [again] = (await draw_up(api_client, headers, "2023-03-01", teacher))["created"]
    assert again["instructor_amount"] == "300000.00"


async def test_a_draft_can_be_thrown_away(
    api_client: AsyncClient, db_session: AsyncSession, headers: dict[str, str], teacher: User
) -> None:
    course = await make_course(db_session, teacher)
    await sell(
        db_session,
        await make_user(db_session),
        [(course, "600000", "0")],
        paid_at=at(date(2023, 3, 3)),
    )
    [statement] = (await draw_up(api_client, headers, "2023-03-01", teacher))["created"]

    response = await api_client.delete(f"{STATEMENTS}/{statement['id']}", headers=headers)

    assert response.status_code == 204
    assert (
        await api_client.get(f"{STATEMENTS}/{statement['id']}", headers=headers)
    ).status_code == 404
    assert len((await draw_up(api_client, headers, "2023-03-01", teacher))["created"]) == 1


async def test_balances_follow_the_money_through_every_state(
    api_client: AsyncClient, db_session: AsyncSession, headers: dict[str, str], teacher: User
) -> None:
    course = await make_course(db_session, teacher)
    buyer = await make_user(db_session)
    await sell(db_session, buyer, [(course, "600000", "0")], paid_at=at(date(2023, 3, 3)))
    await sell(db_session, buyer, [(course, "400000", "0")], paid_at=at(date(2023, 4, 3)))
    [march] = (await draw_up(api_client, headers, "2023-03-01", teacher))["created"]
    await api_client.post(f"{STATEMENTS}/{march['id']}/confirm", headers=headers)

    body = (await api_client.get(BALANCES, headers=headers)).json()

    assert body["settings"] == {
        "minimum": "200000.00",
        "pit_rate": "0.10",
        "pit_threshold": "5000000.00",
    }
    mine = next(b for b in body["items"] if b["instructor"]["id"] == str(teacher.id))
    assert mine["earned_all_time"] == "500000.00"
    assert mine["unbilled"] == "200000.00"
    assert mine["unbilled_lines"] == 1
    assert mine["confirmed_unpaid"] == "300000.00"
    assert mine["paid_out"] == "0.00"


async def test_statements_are_listed_filtered_and_exported(
    api_client: AsyncClient, db_session: AsyncSession, headers: dict[str, str], teacher: User
) -> None:
    course = await make_course(db_session, teacher, title="Khóa xuất Excel")
    await sell(
        db_session,
        await make_user(db_session),
        [(course, "600000", "0")],
        paid_at=at(date(2023, 3, 3)),
    )
    [statement] = (await draw_up(api_client, headers, "2023-03-01", teacher))["created"]

    listed = await api_client.get(
        STATEMENTS, params={"status": "draft", "instructor_id": str(teacher.id)}, headers=headers
    )
    one = await api_client.get(f"{STATEMENTS}/{statement['id']}/export.xlsx", headers=headers)
    everything = await api_client.get("/api/v1/admin/payouts/export.xlsx", headers=headers)

    assert [s["id"] for s in listed.json()["items"]] == [statement["id"]]
    book = load_workbook(BytesIO(one.content))
    assert book.sheetnames == ["Bảng kê", "Dòng bán", "Định nghĩa"]
    header = {row[0]: row[1] for row in book["Bảng kê"].iter_rows(values_only=True) if row[0]}
    assert header["Mã bảng kê"] == statement["code"]
    assert header["Số tiền thực chi"] == 300000
    lines = [r for r in book["Dòng bán"].iter_rows(values_only=True) if r[2] == "Khóa xuất Excel"]
    assert len(lines) == 1 and lines[0][7] == 300000
    overview = load_workbook(BytesIO(everything.content))
    assert overview.sheetnames == ["Số dư giảng viên", "Bảng kê"]


def test_the_tax_rule_on_its_own() -> None:
    assert payouts.tax_for(Decimal("4999999.00")) == Decimal("0.00")
    assert payouts.tax_for(Decimal("5000000.00")) == Decimal("500000.00")
    assert payouts.tax_for(Decimal("5000009.00")) == Decimal("500000.00")
    assert payouts.tax_for(Decimal("9000000.00"), withhold=False) == Decimal("0.00")
