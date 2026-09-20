"""Embed the catalogue now, without waiting for 02:30 or pressing publish.

    python -m scripts.rebuild_course_embeddings
    python -m scripts.rebuild_course_embeddings python-co-ban-cho-nguoi-moi-bat-dau
    python -m scripts.rebuild_course_embeddings --dry-run

Same two reasons as `scripts/rebuild_recommendations.py` and
`scripts/ingest_course.py`. A demo cannot wait for a cron: until the vectors
exist, every course page shows an empty "Khóa học tương tự" block, which looks
like a broken feature rather than an unfilled table. And the thesis has to be
reproducible -- a precision@k measured on a ranking nobody else can regenerate
is not a measurement.

It calls the same `rebuild_embeddings` the Celery task calls, against the same
database and the same Gemini key, so what it writes is what the nightly job
would have written. `--dry-run` prints the text each course *would* be embedded
as and spends no quota, which answers the question that comes up first: is the
description being cut, and is what survives the part that says what the course
is about.
"""

import argparse
import asyncio
import sys
import uuid

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import Category, Course
from app.services.content_based import course_text, rebuild_embeddings
from app.services.llm import LLMError, build_embedder


async def _resolve(session, wanted: str) -> Course:
    """A course by slug, or by id if that is what was typed."""
    course = await session.scalar(
        select(Course).where(Course.slug == wanted, Course.deleted_at.is_(None))
    )
    if course is not None:
        return course

    try:
        course_id = uuid.UUID(wanted)
    except ValueError:
        raise SystemExit(f"Không tìm thấy khóa học '{wanted}'") from None

    course = await session.scalar(
        select(Course).where(Course.id == course_id, Course.deleted_at.is_(None))
    )
    if course is None:
        raise SystemExit(f"Không tìm thấy khóa học '{wanted}'")
    return course


async def _preview(session, course_ids: list[uuid.UUID] | None) -> None:
    """What would be embedded, without embedding it."""
    query = (
        select(Course, Category.name)
        .join(Category, Category.id == Course.category_id)
        .where(Course.status == "published", Course.deleted_at.is_(None))
        .order_by(Course.created_at, Course.id)
    )
    if course_ids is not None:
        query = query.where(Course.id.in_(course_ids))

    for course, category_name in (await session.execute(query)).all():
        text = course_text(course, category_name)
        print(f"\n--- {course.slug} ({len(text)} ký tự) ---")
        print(text)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "course",
        nargs="?",
        help="slug hoặc id của một khóa học; bỏ trống để làm cả catalogue",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="in ra văn bản sẽ nhúng, không gọi API và không ghi gì",
    )
    args = parser.parse_args()

    async with SessionLocal() as session:
        course_ids = None
        if args.course:
            course = await _resolve(session, args.course)
            if course.status != "published":
                raise SystemExit(
                    f"Khóa '{course.slug}' đang ở trạng thái '{course.status}'; "
                    "chỉ khóa đã xuất bản mới được nhúng."
                )
            course_ids = [course.id]

        if args.dry_run:
            await _preview(session, course_ids)
            return

        try:
            embedder = build_embedder()
        except LLMError as error:
            print(error.message, file=sys.stderr)
            raise SystemExit(1) from error

        report = await rebuild_embeddings(
            session, embedder=embedder, course_ids=course_ids
        )

    print(
        f"Đã nhúng {report.embedded} khóa học "
        f"({report.unchanged} khóa không đổi, không tốn quota) "
        f"bằng model {embedder.model}."
    )
    if report.embedded == 0 and report.unchanged == 0:
        print(
            "Không có khóa nào để nhúng: chưa có khóa học nào đã xuất bản. "
            "Chạy `python -m scripts.seed` trước."
        )


if __name__ == "__main__":
    asyncio.run(main())
