"""Instructor tiers: what each number means, who decides, and what a sale keeps.

* A sale is **frozen at the rate of the instructor's tier when it is paid** --
  through the real IPN and the real 0 đ checkout -- and a promotion afterwards
  does not reprice it.
* The numbers are **hard to pump**: a buyer only counts as a paid student when
  they paid a real price through a gateway; the rating is a Bayesian average
  of buyers' reviews; completion waits 30 days; Q&A needs five questions
  before it can fail.
* **The system suggests, an admin decides**, with a note, and the instructor
  is told. The ladder stays a ladder.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from io import BytesIO

import pytest
from httpx import AsyncClient
from openpyxl import load_workbook
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    InstructorTier,
    InstructorTierChange,
    Notification,
    Order,
    OrderItem,
    QaReply,
    QaThread,
    Report,
    Review,
    User,
)
from app.services import instructor_tiers as tiers_service
from tests.api.test_commerce import make_course, make_user, sign_in
from tests.api.test_coupons import make_coupon
from tests.api.test_instructor_stats import add_lessons, enrol, sell
from tests.api.test_orders import (  # noqa: F401 -- vnpay_configured is a fixture
    add,
    callback,
    checkout,
    send_ipn,
    vnpay_configured,
)

TIERS = "/api/v1/admin/tiers"
REVIEW = "/api/v1/admin/instructor-tiers"
MY_TIER = "/api/v1/instructor/tier"


@pytest.fixture
async def owner(db_session: AsyncSession) -> User:
    return await make_user(db_session, "instructor")


@pytest.fixture
async def admin(db_session: AsyncSession) -> User:
    return await make_user(db_session, "admin")


async def tier(session: AsyncSession, code: str) -> InstructorTier:
    return await session.scalar(select(InstructorTier).where(InstructorTier.code == code))


async def frozen_rates(session: AsyncSession, order_code: str) -> list[Decimal]:
    return list(
        await session.scalars(
            select(OrderItem.instructor_share_rate)
            .join(Order, Order.id == OrderItem.order_id)
            .where(Order.code == order_code)
        )
    )


# --- The rate a sale keeps -----------------------------------------------------


@pytest.mark.usefixtures("vnpay_configured")
async def test_a_paid_sale_keeps_the_rate_of_the_tier_it_was_sold_at(
    api_client: AsyncClient,
    db_session: AsyncSession,
    owner: User,
    admin: User,
) -> None:
    """Sold on the first tier, paid through the IPN: 50 %. The instructor is
    then promoted; that sale stays at 50 % and the next one is at 55 %."""
    first = await make_course(db_session, owner, price="199000")
    second = await make_course(db_session, owner, price="299000")
    buyer = await make_user(db_session)
    headers = await sign_in(api_client, buyer)

    await add(api_client, first, headers)
    order = await checkout(api_client, headers)
    pending = await frozen_rates(db_session, order["code"])
    assert pending == [None]  # nothing is frozen before the money arrives
    await send_ipn(api_client, callback(order["code"], order["total"]))
    assert await frozen_rates(db_session, order["code"]) == [Decimal("0.5000")]

    await tiers_service.set_tier(
        db_session, admin, owner.id, (await tier(db_session, "dan-duong")).id, "Lên cấp"
    )
    await add(api_client, second, headers)
    later = await checkout(api_client, headers)
    await send_ipn(api_client, callback(later["code"], later["total"], transaction_no="999"))

    assert await frozen_rates(db_session, order["code"]) == [Decimal("0.5000")]
    assert await frozen_rates(db_session, later["code"]) == [Decimal("0.5500")]


async def test_a_zero_dong_checkout_freezes_a_rate_too(
    api_client: AsyncClient, db_session: AsyncSession, owner: User
) -> None:
    course = await make_course(db_session, owner, price="199000")
    await make_coupon(db_session, code="MIENPHI100", discount_type="percent", value="100")
    buyer = await make_user(db_session)
    headers = await sign_in(api_client, buyer)
    await add(api_client, course, headers)

    order = await checkout(api_client, headers, coupon="MIENPHI100")

    assert order["status"] == "paid"
    assert await frozen_rates(db_session, order["code"]) == [Decimal("0.5000")]


async def test_editing_a_tier_rate_reprices_nothing_already_sold(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, admin: User
) -> None:
    course = await make_course(db_session, owner)
    buyer = await make_user(db_session)
    order = await sell(db_session, buyer, [(course, "199000", "0")], paid_at=datetime.now(UTC))
    base = await tier(db_session, "khoi-hanh")

    response = await api_client.patch(
        f"{TIERS}/{base.id}",
        json={"share_rate": "0.4500"},
        headers=await sign_in(api_client, admin),
    )

    assert response.status_code == 200, response.text
    assert response.json()["share_rate"] == "0.4500"
    assert await frozen_rates(db_session, order.code) == [Decimal("0.5000")]
    rates = await tiers_service.share_rates(db_session, [course.id])
    assert rates[course.id] == Decimal("0.4500")


@pytest.mark.parametrize(
    ("code", "rate"),
    [("dan-duong", "0.4900"), ("dan-duong", "0.6100")],
)
async def test_the_ladder_stays_a_ladder(
    api_client: AsyncClient, db_session: AsyncSession, admin: User, code: str, rate: str
) -> None:
    """A tier's rate may not drop under the one below or rise over the one above."""
    step = await tier(db_session, code)

    response = await api_client.patch(
        f"{TIERS}/{step.id}", json={"share_rate": rate}, headers=await sign_in(api_client, admin)
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "TIER_LADDER_BROKEN"


async def test_a_required_threshold_cannot_be_cleared(
    api_client: AsyncClient, db_session: AsyncSession, admin: User
) -> None:
    step = await tier(db_session, "mo-loi")
    headers = await sign_in(api_client, admin)

    cleared = await api_client.patch(
        f"{TIERS}/{step.id}", json={"min_paid_students": None}, headers=headers
    )
    optional = await api_client.patch(
        f"{TIERS}/{step.id}", json={"min_completion_rate": None}, headers=headers
    )

    assert cleared.status_code == 422
    assert optional.status_code == 200
    assert optional.json()["min_completion_rate"] is None


# --- What the numbers mean -------------------------------------------------------


async def test_only_buyers_who_paid_a_real_price_are_paid_students(
    db_session: AsyncSession, owner: User
) -> None:
    """Counted: a full-price buyer, and one with a 50 % coupon. Not counted: a
    0 đ checkout, a 90 % coupon (under 30 % of the price), a locked account, a
    buyer whose order never got paid -- and the full-price buyer is one person
    however many courses they bought."""
    first = await make_course(db_session, owner, price="200000")
    second = await make_course(db_session, owner, price="200000")
    now = datetime.now(UTC)
    full, half, gratis, cheap, locked, unpaid = [await make_user(db_session) for _ in range(6)]
    await sell(db_session, full, [(first, "200000", "0"), (second, "200000", "0")], paid_at=now)
    await sell(db_session, half, [(first, "200000", "100000")], paid_at=now)
    await sell(db_session, gratis, [(first, "200000", "200000")], paid_at=now, provider="none")
    await sell(db_session, cheap, [(first, "200000", "180000")], paid_at=now)
    await sell(db_session, locked, [(first, "200000", "0")], paid_at=now)
    await sell(db_session, unpaid, [(first, "200000", "0")], paid_at=None, status="pending")
    locked.locked_at = now
    await db_session.flush()

    evaluation = await tiers_service.evaluate(db_session, owner.id)

    assert evaluation.metrics.paid_students == 2
    # Revenue is every paid line of the last year, whatever it cost.
    assert evaluation.metrics.revenue_12m == Decimal("720000.00")


async def test_revenue_counts_the_last_365_days_only(db_session: AsyncSession, owner: User) -> None:
    course = await make_course(db_session, owner, price="300000")
    buyer = await make_user(db_session)
    now = datetime.now(UTC)
    await sell(db_session, buyer, [(course, "300000", "0")], paid_at=now - timedelta(days=30))
    await sell(db_session, buyer, [(course, "300000", "0")], paid_at=now - timedelta(days=400))

    evaluation = await tiers_service.evaluate(db_session, owner.id)

    assert evaluation.metrics.revenue_12m == Decimal("300000.00")


async def test_the_rating_is_a_bayesian_average_of_buyers_reviews(
    db_session: AsyncSession, owner: User
) -> None:
    """Two buyers give 5 stars, a free learner gives 1: the free review is not
    counted, and two 5-star reviews pull the 4.0 prior to (10 + 40) / 12."""
    course = await make_course(db_session, owner)
    when = datetime.now(UTC) - timedelta(days=40)
    buyers = [await make_user(db_session) for _ in range(2)]
    freeloader = await make_user(db_session)
    for buyer in buyers:
        await enrol(db_session, buyer, course, when=when, source="purchase")
        db_session.add(Review(course_id=course.id, user_id=buyer.id, rating=5))
    await enrol(db_session, freeloader, course, when=when)
    db_session.add(Review(course_id=course.id, user_id=freeloader.id, rating=1))
    await db_session.flush()

    metrics = (await tiers_service.evaluate(db_session, owner.id)).metrics

    assert metrics.reviews == 2
    assert metrics.rating_raw == 5.0
    assert metrics.rating == round((10 + 4.0 * 10) / 12, 2)


async def test_completion_waits_thirty_days_and_counts_paid_enrolments(
    db_session: AsyncSession, owner: User
) -> None:
    course = await make_course(db_session, owner)
    now = datetime.now(UTC)
    old = now - timedelta(days=45)
    await enrol(
        db_session, await make_user(db_session), course, when=old, completed=True, source="purchase"
    )
    await enrol(db_session, await make_user(db_session), course, when=old, source="purchase")
    # Too young to judge, and a free enrolment: neither counts.
    await enrol(db_session, await make_user(db_session), course, when=now, source="purchase")
    await enrol(db_session, await make_user(db_session), course, when=old, completed=True)

    metrics = (await tiers_service.evaluate(db_session, owner.id)).metrics

    assert metrics.completion_base == 2
    assert metrics.completion_rate == 0.5


async def test_qa_is_answers_within_48_hours_and_needs_five_questions_to_fail(
    db_session: AsyncSession, owner: User
) -> None:
    course = await make_course(db_session, owner)
    [lesson] = await add_lessons(db_session, course, 1)
    asker = await make_user(db_session)
    now = datetime.now(UTC)

    async def ask(answer_after: timedelta | None, asked_days_ago: int = 5) -> None:
        asked = now - timedelta(days=asked_days_ago)
        thread = QaThread(
            lesson_id=lesson.id, user_id=asker.id, title="?", body="?", created_at=asked
        )
        db_session.add(thread)
        await db_session.flush()
        if answer_after is not None:
            db_session.add(
                QaReply(
                    thread_id=thread.id,
                    user_id=owner.id,
                    body="Trả lời",
                    is_instructor_reply=True,
                    created_at=asked + answer_after,
                )
            )
            await db_session.flush()

    for _ in range(3):
        await ask(timedelta(hours=5))
    await ask(timedelta(hours=60))  # answered, but late
    await ask(None)  # never answered
    await ask(None, asked_days_ago=0)  # too fresh to count either way
    await ask(timedelta(hours=1), asked_days_ago=120)  # outside the 90 days

    metrics = (await tiers_service.evaluate(db_session, owner.id)).metrics

    assert metrics.qa_questions == 5
    assert metrics.qa_answer_rate == 0.6


async def test_a_course_taken_down_after_a_report_breaks_good_standing(
    db_session: AsyncSession, owner: User
) -> None:
    course = await make_course(db_session, owner)
    reporter = await make_user(db_session)
    db_session.add(
        Report(
            reporter_id=reporter.id,
            target_type="course",
            target_id=course.id,
            reason="copyright",
            status="resolved",
            resolved_at=datetime.now(UTC) - timedelta(days=10),
            content_removed=True,
        )
    )
    await db_session.flush()

    evaluation = await tiers_service.evaluate(db_session, owner.id)

    assert evaluation.metrics.removed_courses_90d == 1
    standing = next(c for c in evaluation.checks[1].criteria if c.key == "good_standing")
    assert standing.met is False


# --- Suggestion and decision -----------------------------------------------------


async def make_eligible_for_second_tier(session: AsyncSession, owner: User) -> None:
    """20 paid students at 250 000 đ (5 000 000 đ), five 5-star buyer reviews,
    a first course published three months ago."""
    course = await make_course(session, owner, price="250000")
    course.published_at = datetime.now(UTC) - timedelta(days=95)
    now = datetime.now(UTC)
    for index in range(20):
        buyer = await make_user(session)
        await sell(session, buyer, [(course, "250000", "0")], paid_at=now - timedelta(days=10))
        await enrol(session, buyer, course, when=now - timedelta(days=10), source="purchase")
        if index < 5:
            session.add(Review(course_id=course.id, user_id=buyer.id, rating=5))
    await session.flush()


async def test_numbers_that_reach_a_tier_suggest_it_and_nothing_moves(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, admin: User
) -> None:
    await make_eligible_for_second_tier(db_session, owner)

    response = await api_client.get(
        f"{REVIEW}/{owner.id}", headers=await sign_in(api_client, admin)
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["current"]["code"] == "khoi-hanh"
    assert body["suggested"]["code"] == "dan-duong"
    assert "eligible" in body["flags"]
    assert body["metrics"]["paid_students"] == 20
    assert body["metrics"]["revenue_12m"] == "5000000.00"
    second = next(c for c in body["checks"] if c["tier"]["code"] == "dan-duong")
    assert second["met"] is True
    # The admin sees the money criteria with their numbers.
    revenue = next(c for c in second["criteria"] if c["key"] == "revenue_12m")
    assert revenue["admin_only"] is True and "5.000.000" in revenue["value"]

    mine = (await api_client.get(MY_TIER, headers=await sign_in(api_client, owner))).json()
    assert mine["current"]["code"] == "khoi-hanh"
    assert mine["eligible"] is True
    assert mine["next"]["tier"]["code"] == "dan-duong"


async def test_an_admin_decision_moves_the_tier_records_why_and_tells_them(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, admin: User
) -> None:
    target = await tier(db_session, "mo-loi")
    headers = await sign_in(api_client, admin)

    response = await api_client.post(
        f"{REVIEW}/{owner.id}",
        json={"tier_id": str(target.id), "note": "  Chất lượng nội dung vượt trội  "},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["current"]["code"] == "mo-loi"
    await db_session.refresh(owner)
    assert owner.instructor_tier_id == target.id

    change = await db_session.scalar(
        select(InstructorTierChange).where(InstructorTierChange.instructor_id == owner.id)
    )
    assert change.note == "Chất lượng nội dung vượt trội"
    assert change.decided_by == admin.id
    assert "paid_students" in change.metrics

    notification = await db_session.scalar(
        select(Notification).where(Notification.user_id == owner.id)
    )
    assert notification.type == "instructor_tier_changed"
    assert notification.payload["to_tier"] == "Mở lối"
    assert notification.payload["from_tier"] == "Khởi hành"

    history = (await api_client.get(f"{REVIEW}/{owner.id}/history", headers=headers)).json()
    assert [h["to_tier"]["code"] for h in history] == ["mo-loi"]
    assert history[0]["decided_by"]["id"] == str(admin.id)

    mine = (await api_client.get(MY_TIER, headers=await sign_in(api_client, owner))).json()
    assert mine["current"]["code"] == "mo-loi"
    assert mine["history"][0]["note"] == "Chất lượng nội dung vượt trội"


async def test_a_decision_needs_a_reason_and_a_change(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, admin: User
) -> None:
    headers = await sign_in(api_client, admin)
    base = await tier(db_session, "khoi-hanh")

    blank = await api_client.post(
        f"{REVIEW}/{owner.id}", json={"tier_id": str(base.id), "note": "   "}, headers=headers
    )
    same = await api_client.post(
        f"{REVIEW}/{owner.id}",
        json={"tier_id": str(base.id), "note": "Giữ nguyên"},
        headers=headers,
    )

    assert blank.status_code == 422
    assert same.status_code == 409
    assert same.json()["detail"]["code"] == "TIER_UNCHANGED"


async def test_only_instructors_have_a_tier(
    api_client: AsyncClient, db_session: AsyncSession, admin: User
) -> None:
    student = await make_user(db_session)
    target = await tier(db_session, "dan-duong")
    headers = await sign_in(api_client, admin)

    got = await api_client.get(f"{REVIEW}/{student.id}", headers=headers)
    moved = await api_client.post(
        f"{REVIEW}/{student.id}", json={"tier_id": str(target.id), "note": "?"}, headers=headers
    )

    assert got.status_code == 404
    assert moved.status_code == 404
    assert moved.json()["detail"]["code"] == "INSTRUCTOR_NOT_FOUND"


async def test_falling_under_the_maintenance_bar_flags_but_does_not_demote(
    db_session: AsyncSession, owner: User, admin: User
) -> None:
    """Promoted to the third tier with nothing to show for it: flagged for the
    admin, still on the third tier."""
    await tiers_service.set_tier(
        db_session, admin, owner.id, (await tier(db_session, "mo-loi")).id, "Thử"
    )

    evaluation = await tiers_service.evaluate(db_session, owner.id)

    assert evaluation.current.code == "mo-loi"
    assert evaluation.keeps_current is False
    assert "below_maintenance" in evaluation.flags
    assert "recently_changed" in evaluation.flags


def test_keeping_a_tier_is_easier_than_reaching_it() -> None:
    step = InstructorTier(
        code="x",
        name="X",
        rank=2,
        share_rate=Decimal("0.55"),
        min_paid_students=20,
        min_revenue_12m=Decimal("5000000"),
        min_rating=Decimal("4.00"),
        min_reviews=5,
        min_completion_rate=None,
        min_qa_answer_rate=Decimal("0.60"),
        min_published_courses=1,
        min_months_active=2,
    )
    metrics = tiers_service.Metrics(
        paid_students=16,
        revenue_12m=Decimal("4000000"),
        reviews=5,
        rating=3.8,
        qa_questions=10,
        qa_answer_rate=0.5,
        published_courses=1,
        months_active=2,
    )

    assert tiers_service.check(step, metrics).met is False
    assert tiers_service.check(step, metrics, maintain=True).met is True


async def test_the_review_list_and_its_export(
    api_client: AsyncClient, db_session: AsyncSession, owner: User, admin: User
) -> None:
    headers = await sign_in(api_client, admin)

    listing = await api_client.get(REVIEW, headers=headers)
    export = await api_client.get(f"{REVIEW}/export.xlsx", headers=headers)
    ladder = await api_client.get(TIERS, headers=headers)

    assert listing.status_code == 200
    assert str(owner.id) in {row["instructor"]["id"] for row in listing.json()}
    assert [t["rank"] for t in ladder.json()] == [1, 2, 3, 4, 5]
    assert [t["share_rate"] for t in ladder.json()] == [
        "0.5000",
        "0.5500",
        "0.6000",
        "0.6500",
        "0.7000",
    ]
    book = load_workbook(BytesIO(export.content))
    assert book.sheetnames == ["Xét cấp", "Bậc thang"]
    emails = [row[1].value for row in book["Xét cấp"].iter_rows()]
    assert owner.email in emails
