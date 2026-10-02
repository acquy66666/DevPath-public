"""Remove everything the end-to-end tests left behind on this database.

    python -m scripts.purge_e2e [--dry-run]

Each run of the Playwright suite (frontend/e2e) signs up a student and an
instructor, puts a course on sale, buys it and earns a certificate -- real rows,
through the real API, on whatever stack it ran against. On CI that database is
thrown away with the job; on a developer machine the courses pile up in the
catalogue and the student on the leaderboard. Every account the suite creates
has an address under `E2E_DOMAIN`, and that address is what this script goes by:
those accounts, the courses they wrote, and whatever hangs off either.

Deleted in the order the foreign keys allow -- five of them are RESTRICT on
purpose, so nothing else removes a paid order or a certificate by accident:

  orders           (orders.user_id, order_items.course_id are RESTRICT)
  certificates     (certificates.enrollment_id is RESTRICT)
  enrolments in the suite's courses, then the courses
                   (enrollments.course_id, courses.instructor_id are RESTRICT)
  the accounts     (everything else they own cascades)

Then the student counts of any other course a suite account had joined are
recounted, and the leaderboard is rebuilt from the XP ledger without them.
"""

import argparse
import asyncio
from dataclasses import dataclass

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.models import Course, Enrollment, Order, OrderItem, User
from app.services import certificates, course_stats
from app.services.leaderboard import get_board, rebuild_current, today_in_vietnam

#: The suite's addresses (frontend/e2e/support/stack.ts and the spec).
E2E_DOMAIN = "@e2e.devpath.example"


@dataclass(frozen=True)
class Purged:
    users: int
    courses: int
    orders: int
    certificates: int


def _suite_users():
    return select(User.id).where(User.email.like(f"%{E2E_DOMAIN}"))


def _suite_courses():
    return select(Course.id).where(Course.instructor_id.in_(_suite_users()))


async def count(session: AsyncSession) -> tuple[int, int]:
    """(accounts, courses) the suite has left here."""
    users = await session.scalar(select(func.count()).select_from(_suite_users().subquery()))
    courses = await session.scalar(select(func.count()).select_from(_suite_courses().subquery()))
    return users or 0, courses or 0


async def purge(session: AsyncSession) -> Purged:
    """Delete it all. Does not commit; the caller does."""
    users = _suite_users()
    courses = _suite_courses()

    # Courses outside the suite that a suite account had joined: their
    # student counts drop once the account is gone.
    touched = list(
        await session.scalars(
            select(Enrollment.course_id)
            .where(Enrollment.user_id.in_(users), Enrollment.course_id.not_in(courses))
            .distinct()
        )
    )

    orders = await session.execute(
        delete(Order).where(
            or_(
                Order.user_id.in_(users),
                Order.id.in_(select(OrderItem.order_id).where(OrderItem.course_id.in_(courses))),
            )
        )
    )
    issued = await certificates.delete_for_enrollments(
        session,
        select(Enrollment.id).where(
            or_(Enrollment.user_id.in_(users), Enrollment.course_id.in_(courses))
        ),
    )
    await session.execute(delete(Enrollment).where(Enrollment.course_id.in_(courses)))
    removed_courses = await session.execute(delete(Course).where(Course.id.in_(courses)))
    removed_users = await session.execute(delete(User).where(User.email.like(f"%{E2E_DOMAIN}")))
    await session.flush()

    if touched:
        await course_stats.rebuild(session, touched)
        await session.flush()

    return Purged(
        users=removed_users.rowcount or 0,
        courses=removed_courses.rowcount or 0,
        orders=orders.rowcount or 0,
        certificates=issued,
    )


async def main(dry_run: bool) -> None:
    async with SessionLocal() as session:
        if dry_run:
            users, courses = await count(session)
            print(f"Sẽ gỡ {users} tài khoản và {courses} khóa học do bộ E2E để lại.")
            return

        purged = await purge(session)
        await session.commit()

        # After the commit: the board is a view of the committed XP ledger.
        await rebuild_current(session, get_board(), today=today_in_vietnam())

    print(
        f"Đã gỡ {purged.users} tài khoản, {purged.courses} khóa học, "
        f"{purged.orders} đơn hàng và {purged.certificates} chứng chỉ do bộ E2E để lại; "
        "bảng xếp hạng đã dựng lại."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="chỉ đếm, không xóa")
    asyncio.run(main(parser.parse_args().dry_run))
