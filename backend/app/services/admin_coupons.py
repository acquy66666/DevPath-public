"""The admin's campaigns: creating discount codes, changing them, ending them.

The rules a code must obey live in the table (`models/coupon.py` -- upper-case,
at least three characters, a percentage no higher than 100, an end after the
start, never more uses than allowed); the request schemas repeat them so a form
gets a 422 with a sentence instead of a 500 from a CHECK. What only this module
decides:

* **The code never changes once made.** It is printed on leaflets and typed
  into carts; a campaign that needs another code is another campaign.
* **Everything else may change**, and past orders do not move: an order froze
  its subtotal, discount and each line's share when it was placed.
* **The limit cannot drop below what has been used**, or the row would say a
  campaign ran over its own limit (`ck_coupons_uses_left` would refuse it too).
* **Ending early is setting `valid_to` to now** -- the table has no `is_active`
  on purpose. A campaign that has not started yet cannot be "ended"; its dates
  are edited, or it is deleted.
* **A code that has been used is never deleted.** It is the name of a
  discount on real orders; it is ended instead. An unused one may go.

Status is derived from the dates and the count, never stored: `scheduled`
(starts later), `live`, `exhausted` (limit reached), `ended` (past `valid_to`).
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from fastapi import status
from sqlalchemy import ColumnElement, and_, delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DomainError
from app.models import Coupon, CouponCourse, Course
from app.services.coupons import normalize
from app.services.courses import CourseNotFoundError

CouponStatus = Literal["scheduled", "live", "exhausted", "ended"]
CouponStatusFilter = Literal["all", "scheduled", "live", "exhausted", "ended"]


class CouponCodeTakenError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    code = "COUPON_CODE_TAKEN"


class CouponNotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "COUPON_NOT_FOUND"


class CouponLimitBelowUsedError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    code = "COUPON_LIMIT_BELOW_USED"


class CouponPeriodError(DomainError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "INVALID_COUPON_PERIOD"


class CouponValueError(DomainError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "INVALID_COUPON_VALUE"


class CouponNotStartedError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    code = "COUPON_NOT_STARTED"


class CouponUsedError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    code = "COUPON_IN_USE"


@dataclass(frozen=True, slots=True)
class CourseRef:
    id: uuid.UUID
    title: str


@dataclass(frozen=True, slots=True)
class AdminCoupon:
    coupon: Coupon
    status: CouponStatus
    courses: list[CourseRef]


def status_of(coupon: Coupon, now: datetime) -> CouponStatus:
    if coupon.valid_to is not None and coupon.valid_to <= now:
        return "ended"
    if coupon.valid_from > now:
        return "scheduled"
    if coupon.max_uses is not None and coupon.used_count >= coupon.max_uses:
        return "exhausted"
    return "live"


def _status_filter(wanted: CouponStatusFilter, now: datetime) -> ColumnElement[bool] | None:
    not_ended = or_(Coupon.valid_to.is_(None), Coupon.valid_to > now)
    exhausted = and_(Coupon.max_uses.is_not(None), Coupon.used_count >= Coupon.max_uses)
    if wanted == "ended":
        return Coupon.valid_to <= now
    if wanted == "scheduled":
        return and_(Coupon.valid_from > now, not_ended)
    if wanted == "exhausted":
        return and_(Coupon.valid_from <= now, not_ended, exhausted)
    if wanted == "live":
        return and_(Coupon.valid_from <= now, not_ended, ~exhausted)
    return None


async def _courses_of(
    session: AsyncSession, coupon_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[CourseRef]]:
    if not coupon_ids:
        return {}
    rows = await session.execute(
        select(CouponCourse.coupon_id, Course.id, Course.title)
        .join(Course, Course.id == CouponCourse.course_id)
        .where(CouponCourse.coupon_id.in_(coupon_ids))
        .order_by(Course.title)
    )
    found: dict[uuid.UUID, list[CourseRef]] = {}
    for coupon_id, course_id, title in rows:
        found.setdefault(coupon_id, []).append(CourseRef(id=course_id, title=title))
    return found


async def list_coupons(
    session: AsyncSession,
    *,
    status_filter: CouponStatusFilter,
    q: str | None,
    page: int,
    page_size: int,
    now: datetime | None = None,
) -> tuple[list[AdminCoupon], int]:
    """Newest first. `q` matches the code."""
    now = now or datetime.now(UTC)
    listing = select(Coupon)
    condition = _status_filter(status_filter, now)
    if condition is not None:
        listing = listing.where(condition)
    if q:
        listing = listing.where(Coupon.code.contains(normalize(q), autoescape=True))

    total = await session.scalar(select(func.count()).select_from(listing.subquery()))
    coupons = list(
        await session.scalars(
            listing.order_by(Coupon.created_at.desc(), Coupon.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    courses = await _courses_of(session, [coupon.id for coupon in coupons])
    return [
        AdminCoupon(
            coupon=coupon, status=status_of(coupon, now), courses=courses.get(coupon.id, [])
        )
        for coupon in coupons
    ], total or 0


async def _view(session: AsyncSession, coupon: Coupon) -> AdminCoupon:
    await session.refresh(coupon)
    courses = await _courses_of(session, [coupon.id])
    return AdminCoupon(
        coupon=coupon,
        status=status_of(coupon, datetime.now(UTC)),
        courses=courses.get(coupon.id, []),
    )


async def _get(session: AsyncSession, coupon_id: uuid.UUID) -> Coupon:
    coupon = await session.scalar(select(Coupon).where(Coupon.id == coupon_id).with_for_update())
    if coupon is None:
        raise CouponNotFoundError("Không tìm thấy mã giảm giá")
    return coupon


async def _set_courses(
    session: AsyncSession, coupon: Coupon, course_ids: list[uuid.UUID]
) -> None:
    """Replace the courses a `courses`-scoped coupon covers."""
    wanted = set(course_ids)
    if wanted:
        found = set(
            await session.scalars(
                select(Course.id).where(Course.id.in_(wanted), Course.deleted_at.is_(None))
            )
        )
        if found != wanted:
            raise CourseNotFoundError("Có khóa học trong danh sách không tồn tại hoặc đã bị gỡ")
    await session.execute(delete(CouponCourse).where(CouponCourse.coupon_id == coupon.id))
    session.add_all(CouponCourse(coupon_id=coupon.id, course_id=cid) for cid in wanted)


def _check_period(valid_from: datetime, valid_to: datetime | None) -> None:
    if valid_to is not None and valid_to <= valid_from:
        raise CouponPeriodError("Ngày kết thúc phải sau ngày bắt đầu")


async def create(
    session: AsyncSession,
    *,
    code: str,
    discount_type: str,
    value: Decimal,
    scope: str,
    course_ids: list[uuid.UUID],
    max_uses: int | None,
    valid_from: datetime | None,
    valid_to: datetime | None,
) -> AdminCoupon:
    code = normalize(code)
    valid_from = valid_from or datetime.now(UTC)
    _check_period(valid_from, valid_to)
    if await session.scalar(select(Coupon.id).where(Coupon.code == code)) is not None:
        raise CouponCodeTakenError(f"Mã {code} đã tồn tại")

    coupon = Coupon(
        code=code,
        discount_type=discount_type,
        value=value,
        scope=scope,
        max_uses=max_uses,
        valid_from=valid_from,
        valid_to=valid_to,
    )
    session.add(coupon)
    try:
        await session.flush()
    except IntegrityError:
        # Two admins typing the same code at once: the unique index decides.
        await session.rollback()
        raise CouponCodeTakenError(f"Mã {code} đã tồn tại") from None
    if scope == "courses":
        await _set_courses(session, coupon, course_ids)
    await session.commit()
    return await _view(session, coupon)


async def update(session: AsyncSession, coupon_id: uuid.UUID, changes: dict) -> AdminCoupon:
    """Apply only the fields that were sent (`changes` is the schema's
    `model_dump(exclude_unset=True)`)."""
    coupon = await _get(session, coupon_id)

    if "max_uses" in changes:
        limit = changes["max_uses"]
        if limit is not None and limit < coupon.used_count:
            raise CouponLimitBelowUsedError(
                f"Mã đã được dùng {coupon.used_count} lần, giới hạn không thể thấp hơn"
            )
        coupon.max_uses = limit

    valid_from = changes.get("valid_from", coupon.valid_from) or coupon.valid_from
    valid_to = changes["valid_to"] if "valid_to" in changes else coupon.valid_to
    _check_period(valid_from, valid_to)
    coupon.valid_from, coupon.valid_to = valid_from, valid_to

    if "discount_type" in changes:
        coupon.discount_type = changes["discount_type"]
    if "value" in changes:
        coupon.value = changes["value"]
    if coupon.discount_type == "percent" and coupon.value > 100:
        # Switching a 200.000 ₫ code to "percent" without a new value would be 200%.
        raise CouponValueError("Mức giảm theo phần trăm tối đa là 100")

    if "scope" in changes:
        coupon.scope = changes["scope"]
    if coupon.scope == "courses" and ("course_ids" in changes or "scope" in changes):
        course_ids = changes.get("course_ids") or []
        if not course_ids:
            raise CouponValueError("Mã theo khóa học cần ít nhất một khóa học")
        await _set_courses(session, coupon, course_ids)
    elif coupon.scope == "site":
        await _set_courses(session, coupon, [])

    await session.commit()
    return await _view(session, coupon)


async def end_now(
    session: AsyncSession, coupon_id: uuid.UUID, *, now: datetime | None = None
) -> AdminCoupon:
    """Stop accepting the code from this moment. Ending an ended code is a no-op."""
    now = now or datetime.now(UTC)
    coupon = await _get(session, coupon_id)
    if coupon.valid_from > now:
        raise CouponNotStartedError(
            "Mã chưa bắt đầu nên không kết thúc được — sửa ngày hoặc xóa mã"
        )
    if coupon.valid_to is None or coupon.valid_to > now:
        coupon.valid_to = now
    await session.commit()
    return await _view(session, coupon)


async def delete_coupon(session: AsyncSession, coupon_id: uuid.UUID) -> None:
    coupon = await _get(session, coupon_id)
    if coupon.used_count > 0:
        raise CouponUsedError(
            f"Mã đã được dùng {coupon.used_count} lần — hãy kết thúc sớm thay vì xóa"
        )
    await session.delete(coupon)
    await session.commit()
