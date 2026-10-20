"""The admin's money: revenue over time, rankings, tiers, payouts and profit.

Admin-only, every route -- this is the one place money is shown. Each page has
an `export.xlsx` twin that runs the same service call (`services/exports.py`).
"""

import uuid
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.clock import today_in_vietnam
from app.core.deps import DbSession, require_role
from app.models import InstructorTier, User
from app.schemas.finance import (
    BalanceOut,
    BalancesOut,
    ConcentrationOut,
    CourseMoneyOut,
    CriterionAdminOut,
    EvaluationOut,
    ExpenseCategory,
    ExpenseIn,
    ExpenseOut,
    ExpensePageOut,
    ExpenseUpdateIn,
    FinanceGranularity,
    InstructorMoneyOut,
    LeaderboardsOut,
    MetricsOut,
    MoneyOut,
    MoneyPointOut,
    PaidIn,
    PayoutSettingsOut,
    PayoutStatus,
    PersonOut,
    ProfitColumnOut,
    ProfitOut,
    RankEntryOut,
    RankingOut,
    RevenueBreakdownOut,
    RevenueOut,
    SkippedOut,
    StatementBatchIn,
    StatementBatchOut,
    StatementDetailOut,
    StatementLineOut,
    StatementOut,
    TierAdminOut,
    TierBriefOut,
    TierChangeOut,
    TierCheckOut,
    TierDecisionIn,
    TierUpdateIn,
    VoidIn,
    WithholdingIn,
)
from app.schemas.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, Page
from app.services import excel, exports, finance, payouts, profit, rankings
from app.services import instructor_tiers as tiers_service

router = APIRouter(prefix="/admin", tags=["admin-finance"])

Admin = Annotated[User, Depends(require_role("admin"))]
PageNo = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)]
#: Rows per ranking on screen; the export has all of them.
RANKING_LIMIT = 10
DEFAULT_RANGE_DAYS = 30


def _person(user: User) -> PersonOut:
    return PersonOut.model_validate(user)


def _range(start: date | None, end: date | None, granularity: str) -> finance.Range:
    last = end or today_in_vietnam()
    first = start or last - timedelta(days=DEFAULT_RANGE_DAYS - 1)
    return finance.make_range(first, last, granularity)


StartQ = Annotated[date | None, Query(description="Ngày đầu (giờ VN), mặc định 30 ngày trước")]
EndQ = Annotated[date | None, Query(description="Ngày cuối (giờ VN), mặc định hôm nay")]


# --- Revenue -------------------------------------------------------------------


def _money(item: finance.Money) -> dict:
    return MoneyOut.model_validate(item).model_dump()


@router.get("/finance/revenue", response_model=RevenueOut)
async def get_revenue(
    _: Admin,
    session: DbSession,
    start: StartQ = None,
    end: EndQ = None,
    granularity: FinanceGranularity = "day",
    instructor_id: uuid.UUID | None = None,
) -> RevenueOut:
    """Revenue bucket by bucket (hour .. year), its totals, and the range of
    the same length just before -- for the platform or one instructor."""
    span = _range(start, end, granularity)
    report = await finance.revenue(session, span, instructor_id=instructor_id)
    before = span.previous()
    return RevenueOut(
        start=span.start,
        end=span.end,
        granularity=span.granularity,
        previous_start=before.start,
        previous_end=before.end,
        instructor=_person(report.instructor) if report.instructor else None,
        totals=MoneyOut.model_validate(report.totals),
        previous=MoneyOut.model_validate(report.previous),
        series=[MoneyPointOut.model_validate(point) for point in report.series],
    )


def _instructor_money(item: finance.InstructorMoney) -> InstructorMoneyOut:
    assert item.instructor is not None and item.tier is not None
    return InstructorMoneyOut(
        **_money(item),
        instructor=_person(item.instructor),
        tier=TierBriefOut.model_validate(item.tier),
        courses_sold=item.courses_sold,
        share_of_paid=item.share_of_paid,
    )


def _course_money(item: finance.CourseMoney) -> CourseMoneyOut:
    assert item.course is not None and item.instructor is not None
    return CourseMoneyOut(
        **_money(item),
        course_id=item.course.id,
        course_title=item.course.title,
        course_slug=item.course.slug,
        instructor=_person(item.instructor),
    )


@router.get("/finance/revenue/breakdown", response_model=RevenueBreakdownOut)
async def get_revenue_breakdown(
    _: Admin,
    session: DbSession,
    start: StartQ = None,
    end: EndQ = None,
    instructor_id: uuid.UUID | None = None,
) -> RevenueBreakdownOut:
    """The range by instructor and by course, most paid first."""
    span = _range(start, end, "year")
    instructors = [] if instructor_id else await finance.by_instructor(session, span)
    courses = await finance.by_course(session, span, instructor_id=instructor_id)
    return RevenueBreakdownOut(
        start=span.start,
        end=span.end,
        instructors=[_instructor_money(item) for item in instructors],
        courses=[_course_money(item) for item in courses],
    )


@router.get("/finance/revenue/export.xlsx", response_class=Response)
async def export_revenue(
    _: Admin,
    session: DbSession,
    start: StartQ = None,
    end: EndQ = None,
    granularity: FinanceGranularity = "day",
    instructor_id: uuid.UUID | None = None,
) -> Response:
    span = _range(start, end, granularity)
    report = await finance.revenue(session, span, instructor_id=instructor_id)
    instructors = [] if instructor_id else await finance.by_instructor(session, span)
    courses = await finance.by_course(session, span, instructor_id=instructor_id)
    lines = await finance.lines(session, span, instructor_id=instructor_id)
    content = exports.revenue(report, instructors, courses, lines)
    return excel.response(content, f"devpath_doanh-thu_{span.start:%Y%m%d}_{span.end:%Y%m%d}.xlsx")


# --- Rankings ------------------------------------------------------------------


@router.get("/finance/rankings", response_model=LeaderboardsOut)
async def get_rankings(
    _: Admin,
    session: DbSession,
    start: StartQ = None,
    end: EndQ = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = RANKING_LIMIT,
) -> LeaderboardsOut:
    """One leaderboard per measure over the range, with the range before."""
    span = _range(start, end, "year")
    boards = await rankings.leaderboards(session, span)
    before = span.previous()
    return LeaderboardsOut(
        start=span.start,
        end=span.end,
        previous_start=before.start,
        previous_end=before.end,
        rankings=[
            RankingOut(
                code=ranking.code,
                group=ranking.group,
                title=ranking.title,
                unit=ranking.unit,
                ascending=ranking.ascending,
                note=ranking.note,
                total_entries=len(ranking.entries),
                entries=[RankEntryOut.model_validate(e) for e in ranking.entries[:limit]],
            )
            for ranking in boards.rankings
        ],
        concentration=ConcentrationOut.model_validate(boards.concentration),
    )


@router.get("/finance/rankings/export.xlsx", response_class=Response)
async def export_rankings(
    _: Admin, session: DbSession, start: StartQ = None, end: EndQ = None
) -> Response:
    span = _range(start, end, "year")
    content = exports.leaderboards(await rankings.leaderboards(session, span))
    return excel.response(content, f"devpath_xep-hang_{span.start:%Y%m%d}_{span.end:%Y%m%d}.xlsx")


# --- Tiers ---------------------------------------------------------------------


async def _tiers_out(session: DbSession) -> list[TierAdminOut]:
    evaluations = await tiers_service.evaluate_all(session)
    counts: dict[uuid.UUID, int] = {}
    for evaluation in evaluations:
        counts[evaluation.current.id] = counts.get(evaluation.current.id, 0) + 1
    return [
        TierAdminOut.model_validate(tier).model_copy(update={"instructors": counts.get(tier.id, 0)})
        for tier in await tiers_service.list_tiers(session)
    ]


@router.get("/tiers", response_model=list[TierAdminOut])
async def list_tiers(_: Admin, session: DbSession) -> list[TierAdminOut]:
    """The ladder: names, share rates, thresholds, and who is on each step."""
    return await _tiers_out(session)


@router.patch("/tiers/{tier_id}", response_model=TierAdminOut)
async def update_tier(
    tier_id: uuid.UUID, body: TierUpdateIn, _: Admin, session: DbSession
) -> TierAdminOut:
    """Edit one step. A new share rate applies to sales from now on only."""
    await tiers_service.update_tier(session, tier_id, body.model_dump(exclude_unset=True))
    return next(tier for tier in await _tiers_out(session) if tier.id == tier_id)


def _brief(tier: InstructorTier) -> TierBriefOut:
    return TierBriefOut.model_validate(tier)


def _change_out(change, from_tier, to_tier, decider) -> TierChangeOut:
    return TierChangeOut(
        id=change.id,
        from_tier=_brief(from_tier) if from_tier else None,
        to_tier=_brief(to_tier),
        decided_by=_person(decider) if decider else None,
        note=change.note,
        metrics=change.metrics,
        created_at=change.created_at,
    )


def _evaluation_out(
    evaluation: tiers_service.Evaluation, tiers: dict[uuid.UUID, InstructorTier]
) -> EvaluationOut:
    last = evaluation.last_change
    return EvaluationOut(
        instructor=_person(evaluation.instructor),
        current=_brief(evaluation.current),
        suggested=_brief(evaluation.suggested),
        keeps_current=evaluation.keeps_current,
        flags=evaluation.flags,
        metrics=MetricsOut.model_validate(evaluation.metrics),
        checks=[
            TierCheckOut(
                tier=_brief(check.tier),
                met=check.met,
                criteria=[CriterionAdminOut.model_validate(c) for c in check.criteria],
            )
            for check in evaluation.checks
            if check.tier.rank > 1
        ],
        last_change=(
            _change_out(
                last,
                tiers.get(last.from_tier_id) if last.from_tier_id else None,
                tiers[last.to_tier_id],
                None,
            )
            if last
            else None
        ),
    )


@router.get("/instructor-tiers", response_model=list[EvaluationOut])
async def list_instructor_tiers(_: Admin, session: DbSession) -> list[EvaluationOut]:
    """Every instructor: their numbers, their tier, and the tier the numbers
    would suggest -- the list an admin promotes from."""
    tiers = {tier.id: tier for tier in await tiers_service.list_tiers(session)}
    return [_evaluation_out(e, tiers) for e in await tiers_service.evaluate_all(session)]


@router.get("/instructor-tiers/export.xlsx", response_class=Response)
async def export_instructor_tiers(_: Admin, session: DbSession) -> Response:
    content = exports.tier_review(
        await tiers_service.evaluate_all(session), await tiers_service.list_tiers(session)
    )
    return excel.response(content, f"devpath_xet-cap-giang-vien_{today_in_vietnam():%Y%m%d}.xlsx")


@router.get("/instructor-tiers/{instructor_id}", response_model=EvaluationOut)
async def get_instructor_tier(
    instructor_id: uuid.UUID, _: Admin, session: DbSession
) -> EvaluationOut:
    tiers = {tier.id: tier for tier in await tiers_service.list_tiers(session)}
    return _evaluation_out(await tiers_service.evaluate(session, instructor_id), tiers)


@router.get("/instructor-tiers/{instructor_id}/history", response_model=list[TierChangeOut])
async def get_instructor_tier_history(
    instructor_id: uuid.UUID, _: Admin, session: DbSession
) -> list[TierChangeOut]:
    await tiers_service.evaluate(session, instructor_id)  # 404 for a non-instructor
    return [_change_out(*row) for row in await tiers_service.history(session, instructor_id)]


@router.post("/instructor-tiers/{instructor_id}", response_model=EvaluationOut)
async def set_instructor_tier(
    instructor_id: uuid.UUID, body: TierDecisionIn, admin: Admin, session: DbSession
) -> EvaluationOut:
    """Move an instructor to a tier, with the reason. They are notified; their
    sales from now on carry the new share rate."""
    evaluation = await tiers_service.set_tier(
        session, admin, instructor_id, body.tier_id, body.note
    )
    tiers = {tier.id: tier for tier in await tiers_service.list_tiers(session)}
    return _evaluation_out(evaluation, tiers)


# --- Payouts -------------------------------------------------------------------


def _statement_out(statement) -> StatementOut:
    return StatementOut.model_validate(statement)


def _detail(view: payouts.StatementView) -> StatementDetailOut:
    return StatementDetailOut(
        **StatementOut.model_validate(view.statement).model_dump(),
        carried_lines=view.carried_lines,
        lines=[StatementLineOut.model_validate(line) for line in view.lines],
    )


@router.get("/payouts/balances", response_model=BalancesOut)
async def get_payout_balances(_: Admin, session: DbSession) -> BalancesOut:
    """What each instructor has earned, what is not on a statement yet, and
    what is drafted, confirmed and paid."""
    return BalancesOut(
        settings=PayoutSettingsOut(
            minimum=payouts.PAYOUT_MINIMUM,
            pit_rate=payouts.PIT_RATE,
            pit_threshold=payouts.PIT_THRESHOLD,
        ),
        items=[
            BalanceOut(
                instructor=_person(balance.instructor),
                earned_all_time=balance.earned_all_time,
                unbilled=balance.unbilled,
                unbilled_lines=balance.unbilled_lines,
                oldest_unbilled=balance.oldest_unbilled,
                in_draft=balance.in_draft,
                confirmed_unpaid=balance.confirmed_unpaid,
                paid_out=balance.paid_out,
                tax_withheld=balance.tax_withheld,
            )
            for balance in await payouts.balances(session)
        ],
    )


@router.get("/payouts/statements", response_model=Page[StatementOut])
async def list_payout_statements(
    _: Admin,
    session: DbSession,
    status_filter: Annotated[PayoutStatus | None, Query(alias="status")] = None,
    instructor_id: uuid.UUID | None = None,
    month: date | None = None,
    page: PageNo = 1,
    page_size: PageSize = DEFAULT_PAGE_SIZE,
) -> Page[StatementOut]:
    items, total = await payouts.list_statements(
        session,
        status_filter=status_filter,
        instructor_id=instructor_id,
        month=month,
        page=page,
        page_size=page_size,
    )
    return Page[StatementOut](
        items=[_statement_out(s) for s in items], total=total, page=page, page_size=page_size
    )


@router.post(
    "/payouts/statements",
    response_model=StatementBatchOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_payout_statements(
    body: StatementBatchIn, admin: Admin, session: DbSession
) -> StatementBatchOut:
    """Draft a statement for each instructor with something to bill up to the
    end of a past month; those under the minimum are carried forward."""
    batch = await payouts.create_for_month(
        session, admin, body.month, instructor_ids=body.instructor_ids or None
    )
    return StatementBatchOut(
        period_start=batch.period_start,
        period_end=batch.period_end,
        created=[_statement_out(s) for s in batch.created],
        skipped=[
            SkippedOut(instructor=_person(s.instructor), amount=s.amount, lines=s.lines)
            for s in batch.skipped
        ],
    )


@router.get("/payouts/export.xlsx", response_class=Response)
async def export_payouts(
    _: Admin,
    session: DbSession,
    status_filter: Annotated[PayoutStatus | None, Query(alias="status")] = None,
    month: date | None = None,
) -> Response:
    statements, _total = await payouts.list_statements(
        session,
        status_filter=status_filter,
        instructor_id=None,
        month=month,
        page=1,
        page_size=100_000,
    )
    content = exports.payout_overview(await payouts.balances(session), statements)
    filename = f"devpath_thanh-toan-giang-vien_{today_in_vietnam():%Y%m%d}.xlsx"
    return excel.response(content, filename)


@router.get("/payouts/statements/{statement_id}", response_model=StatementDetailOut)
async def get_payout_statement(
    statement_id: uuid.UUID, _: Admin, session: DbSession
) -> StatementDetailOut:
    return _detail(await payouts.get_statement(session, statement_id))


@router.get("/payouts/statements/{statement_id}/export.xlsx", response_class=Response)
async def export_payout_statement(
    statement_id: uuid.UUID, _: Admin, session: DbSession
) -> Response:
    view = await payouts.get_statement(session, statement_id)
    return excel.response(exports.statement(view), f"devpath_bang-ke_{view.statement.code}.xlsx")


@router.patch("/payouts/statements/{statement_id}", response_model=StatementDetailOut)
async def update_payout_statement(
    statement_id: uuid.UUID, body: WithholdingIn, _: Admin, session: DbSession
) -> StatementDetailOut:
    """A draft only: switch tax withholding on or off, and its note."""
    note = body.note.strip() if body.note is not None else None
    return _detail(await payouts.set_withholding(session, statement_id, body.withhold, note))


@router.post("/payouts/statements/{statement_id}/confirm", response_model=StatementDetailOut)
async def confirm_payout_statement(
    statement_id: uuid.UUID, admin: Admin, session: DbSession
) -> StatementDetailOut:
    """Lock a draft: its figures are final from here."""
    return _detail(await payouts.confirm(session, admin, statement_id))


@router.post("/payouts/statements/{statement_id}/pay", response_model=StatementDetailOut)
async def pay_payout_statement(
    statement_id: uuid.UUID, body: PaidIn, admin: Admin, session: DbSession
) -> StatementDetailOut:
    """Record the transfer of a confirmed statement, by its bank reference."""
    return _detail(await payouts.mark_paid(session, admin, statement_id, body.reference))


@router.post("/payouts/statements/{statement_id}/void", response_model=StatementDetailOut)
async def void_payout_statement(
    statement_id: uuid.UUID, body: VoidIn, _: Admin, session: DbSession
) -> StatementDetailOut:
    """Cancel an unpaid statement; its lines go back to be billed."""
    return _detail(await payouts.void(session, statement_id, body.reason))


@router.delete("/payouts/statements/{statement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_payout_statement(statement_id: uuid.UUID, _: Admin, session: DbSession) -> None:
    """Throw a draft away; it was never handed over."""
    await payouts.delete_draft(session, statement_id)


# --- Profit --------------------------------------------------------------------


def _profit_column(column: profit.ProfitColumn) -> ProfitColumnOut:
    return ProfitColumnOut(
        start=column.start,
        end=column.end,
        list_amount=column.list_amount,
        discount=column.discount,
        collected=column.collected,
        instructor_share=column.instructor_share,
        platform_revenue=column.platform_revenue,
        gateway_orders=column.gateway_orders,
        gateway_fee=column.gateway_fee,
        expenses=column.expenses,
        operating_expenses=column.operating_expenses,
        profit_before_tax=column.profit_before_tax,
        tax=column.tax,
        retained=column.retained,
        take_rate=column.take_rate,
        gross_margin=column.gross_margin,
        net_margin=column.net_margin,
    )


Year = Annotated[int | None, Query(ge=2020, le=2100)]


@router.get("/finance/profit", response_model=ProfitOut)
async def get_profit(
    _: Admin,
    session: DbSession,
    year: Year = None,
    granularity: Annotated[str, Query(pattern="^(month|quarter)$")] = "month",
) -> ProfitOut:
    """Profit and loss for a year, month by month or quarter by quarter."""
    report = await profit.report(session, year or today_in_vietnam().year, granularity)
    return ProfitOut(
        year=report.year,
        granularity=report.granularity,  # type: ignore[arg-type]
        columns=[_profit_column(c) for c in report.columns],
        total=_profit_column(report.total),
        fee_rate=report.fee_rate,
        fee_source=report.fee_source,
        category_labels=profit.CATEGORY_LABELS,
    )


@router.get("/finance/profit/export.xlsx", response_class=Response)
async def export_profit(
    _: Admin,
    session: DbSession,
    year: Year = None,
    granularity: Annotated[str, Query(pattern="^(month|quarter)$")] = "month",
) -> Response:
    chosen = year or today_in_vietnam().year
    report = await profit.report(session, chosen, granularity)
    expenses, _total, _amount = await profit.list_expenses(
        session, year=chosen, month=None, category=None, page=1, page_size=100_000
    )
    return excel.response(exports.profit_report(report, expenses), f"devpath_lai-lo_{chosen}.xlsx")


def _expense_out(view: profit.ExpenseView) -> ExpenseOut:
    expense = view.expense
    return ExpenseOut(
        id=expense.id,
        incurred_on=expense.incurred_on,
        category=expense.category,  # type: ignore[arg-type]
        description=expense.description,
        amount=expense.amount,
        created_by=_person(view.created_by) if view.created_by else None,
        created_at=expense.created_at,
    )


Month = Annotated[int | None, Query(ge=1, le=12)]


@router.get("/expenses", response_model=ExpensePageOut)
async def list_expenses(
    _: Admin,
    session: DbSession,
    year: Year = None,
    month: Month = None,
    category: ExpenseCategory | None = None,
    page: PageNo = 1,
    page_size: PageSize = DEFAULT_PAGE_SIZE,
) -> ExpensePageOut:
    items, total, amount = await profit.list_expenses(
        session, year=year, month=month, category=category, page=page, page_size=page_size
    )
    return ExpensePageOut(
        items=[_expense_out(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        amount=amount,
    )


@router.get("/expenses/export.xlsx", response_class=Response)
async def export_expenses(
    _: Admin,
    session: DbSession,
    year: Year = None,
    month: Month = None,
    category: ExpenseCategory | None = None,
) -> Response:
    items, _total, amount = await profit.list_expenses(
        session, year=year, month=month, category=category, page=1, page_size=100_000
    )
    scope = "Tất cả" if year is None else (f"Tháng {month}/{year}" if month else f"Năm {year}")
    return excel.response(exports.expenses_sheet(items, amount, scope), "devpath_chi-phi.xlsx")


@router.post("/expenses", response_model=ExpenseOut, status_code=status.HTTP_201_CREATED)
async def create_expense(body: ExpenseIn, admin: Admin, session: DbSession) -> ExpenseOut:
    return _expense_out(await profit.create_expense(session, admin, body.model_dump()))


@router.patch("/expenses/{expense_id}", response_model=ExpenseOut)
async def update_expense(
    expense_id: uuid.UUID, body: ExpenseUpdateIn, _: Admin, session: DbSession
) -> ExpenseOut:
    return _expense_out(
        await profit.update_expense(session, expense_id, body.model_dump(exclude_unset=True))
    )


@router.delete("/expenses/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_expense(expense_id: uuid.UUID, _: Admin, session: DbSession) -> None:
    await profit.delete_expense(session, expense_id)
