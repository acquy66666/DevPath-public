"""Seed the database with the minimum a developer needs to log in and look around.

Idempotent: running it twice changes nothing the second time, so it is safe in
CI, on a teammate's machine, and after every `alembic upgrade head`.

    python -m scripts.seed

The courses themselves live in `scripts/seed_courses.py`, which is where the
four of them and their curricula are written out.
"""

import asyncio
import os
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models import Category, User
from scripts.seed_courses import (
    DEFAULT_INSTRUCTOR_PASSWORD,
    sample_hls_url,
    seed_courses,
)

DEFAULT_ADMIN_EMAIL = "admin@devpath.local"
DEFAULT_ADMIN_PASSWORD = "devpath-admin"

# Two levels, matching the constraint the service layer enforces: a parent has
# parent_id IS NULL, a child points at one parent and has no children itself.
CATEGORY_TREE: list[tuple[str, str, list[tuple[str, str]]]] = [
    (
        "Lập trình web",
        "lap-trinh-web",
        [("Frontend", "frontend"), ("Backend", "backend")],
    ),
    (
        "Ngôn ngữ lập trình",
        "ngon-ngu-lap-trinh",
        [("Python", "python"), ("JavaScript", "javascript")],
    ),
    (
        "Khoa học máy tính",
        "khoa-hoc-may-tinh",
        [("Cấu trúc dữ liệu & giải thuật", "cau-truc-du-lieu-giai-thuat")],
    ),
]


async def seed_admin(session: AsyncSession) -> tuple[User, bool]:
    """Create the admin account, or return the existing one untouched.

    An existing admin is never overwritten: on a long-lived database that
    password may have been changed on purpose.
    """
    email = os.getenv("SEED_ADMIN_EMAIL", DEFAULT_ADMIN_EMAIL).strip().lower()
    password = os.getenv("SEED_ADMIN_PASSWORD", DEFAULT_ADMIN_PASSWORD)

    existing = await session.scalar(select(User).where(User.email == email))
    if existing is not None:
        return existing, False

    admin = User(
        email=email,
        full_name="Quản trị viên",
        password_hash=hash_password(password),
        role="admin",
    )
    session.add(admin)
    await session.flush()
    return admin, True


async def seed_categories(session: AsyncSession) -> int:
    """Insert any category that is missing, matched by slug. Returns how many."""
    created = 0

    for name, slug, children in CATEGORY_TREE:
        parent = await session.scalar(select(Category).where(Category.slug == slug))
        if parent is None:
            parent = Category(name=name, slug=slug, position=created)
            session.add(parent)
            await session.flush()
            created += 1

        for position, (child_name, child_slug) in enumerate(children):
            child = await session.scalar(
                select(Category).where(Category.slug == child_slug)
            )
            if child is None:
                session.add(
                    Category(
                        name=child_name,
                        slug=child_slug,
                        parent_id=parent.id,
                        position=position,
                    )
                )
                created += 1

    # SessionLocal sets autoflush=False, so without this the rows just added are
    # still pending and the course seeding below -- which finds its category by
    # slug -- would not see a single one of them on a fresh database.
    await session.flush()

    return created


async def main() -> None:
    using_default_password = "SEED_ADMIN_PASSWORD" not in os.environ

    using_default_instructor_password = "SEED_INSTRUCTOR_PASSWORD" not in os.environ

    async with SessionLocal() as session:
        admin, admin_created = await seed_admin(session)
        categories_created = await seed_categories(session)
        # After the categories: every course points at one of them by slug.
        instructors_created, courses_created = await seed_courses(session)
        await session.commit()

    status = "created" if admin_created else "already existed"
    print(f"admin      : {admin.email} ({status})")
    print(f"categories : {categories_created} created")
    print(f"instructors: {instructors_created} created")
    print(f"courses    : {courses_created} created")
    print(f"sample HLS : {sample_hls_url()}")

    weak = []
    if admin_created and using_default_password:
        weak.append(f"admin ({DEFAULT_ADMIN_PASSWORD!r}, SEED_ADMIN_PASSWORD)")
    if instructors_created and using_default_instructor_password:
        weak.append(
            f"instructor ({DEFAULT_INSTRUCTOR_PASSWORD!r}, SEED_INSTRUCTOR_PASSWORD)"
        )

    if weak:
        print(
            "\nWARNING: these accounts have built-in default passwords: "
            + "; ".join(weak)
            + ". Set the environment variables named above before seeding "
            "anything reachable from the internet.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    asyncio.run(main())
