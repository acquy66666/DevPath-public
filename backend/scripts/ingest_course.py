"""Ingest a course into `doc_chunks` now, without publishing it again.

    python -m scripts.ingest_course python-co-ban-cho-nguoi-moi-bat-dau
    python -m scripts.ingest_course --all
    python -m scripts.ingest_course --all --dry-run

Same two reasons as `scripts/rebuild_recommendations.py`. A demo cannot wait
for somebody to press publish on four courses, and the thesis has to be
reproducible: an evaluation of the chatbot is worth nothing if the corpus
behind it can only be rebuilt by clicking through the instructor UI in the
right order.

It calls the same `ingest_course` the Celery task calls, against the same
database and the same Gemini key, so what it writes is what the job would have
written. `--dry-run` chunks without embedding, which costs no quota and answers
the question that comes up most often: how many chunks is this going to be, and
what do the boundaries look like.
"""

import argparse
import asyncio
import sys
import uuid

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import Course
from app.services.chunking import chunk_text
from app.services.ingest import ingest_course, lesson_text
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
        raise SystemExit(f"Không tìm thấy khóa học có slug '{wanted}'") from None

    course = await session.scalar(
        select(Course).where(Course.id == course_id, Course.deleted_at.is_(None))
    )
    if course is None:
        raise SystemExit(f"Không tìm thấy khóa học có id '{wanted}'")
    return course


async def _dry_run(session, courses: list[Course]) -> None:
    """What would be embedded, without embedding it."""
    from app.models import CourseSection, Lesson

    grand_total = 0
    for course in courses:
        lessons = list(
            await session.scalars(
                select(Lesson)
                .join(CourseSection, CourseSection.id == Lesson.section_id)
                .where(CourseSection.course_id == course.id)
                .order_by(CourseSection.position, Lesson.position)
            )
        )
        chunks = 0
        with_text = 0
        for lesson in lessons:
            text = lesson_text(lesson)
            if not text:
                continue
            with_text += 1
            chunks += len(chunk_text(text))

        grand_total += chunks
        print(
            f"{course.slug}: {with_text}/{len(lessons)} bài học có chữ "
            f"→ {chunks} chunk"
        )

    print(f"\nTổng: {grand_total} chunk sẽ phải gọi embedding.")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("course", nargs="?", help="Slug hoặc id của khóa học.")
    parser.add_argument(
        "--all",
        action="store_true",
        dest="every",
        help="Nạp mọi khóa học đã xuất bản.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Chỉ đếm chunk, không gọi Gemini và không ghi gì.",
    )
    args = parser.parse_args()

    if not args.every and not args.course:
        parser.error("Cần một slug/id, hoặc --all.")

    async with SessionLocal() as session:
        if args.every:
            courses = list(
                await session.scalars(
                    select(Course)
                    .where(Course.status == "published", Course.deleted_at.is_(None))
                    .order_by(Course.created_at)
                )
            )
            if not courses:
                raise SystemExit("Chưa có khóa học nào được xuất bản.")
        else:
            courses = [await _resolve(session, args.course)]

        if args.dry_run:
            await _dry_run(session, courses)
            return

        try:
            embedder = build_embedder()
        except LLMError as error:
            raise SystemExit(
                f"{error.message}. Đặt GEMINI_API_KEY trong infra/.env rồi thử lại."
            ) from None

        print(f"model embedding: {embedder.model}\n")
        totals = [0, 0, 0, 0, 0]

        for course in courses:
            report = await ingest_course(session, course.id, embedder=embedder)
            totals = [
                totals[0] + report.lessons,
                totals[1] + report.chunks,
                totals[2] + report.unchanged,
                totals[3] + report.skipped,
                totals[4] + report.removed,
            ]
            print(
                f"{course.slug}: {report.lessons} bài nạp mới, "
                f"{report.chunks} chunk, {report.unchanged} bài không đổi, "
                f"{report.skipped} bài không có chữ"
                + (f", {report.removed} bài hết chữ đã gỡ chunk" if report.removed else "")
            )

        if len(courses) > 1:
            print(
                f"\nTổng: {totals[0]} bài nạp mới, {totals[1]} chunk, "
                f"{totals[2]} bài không đổi, {totals[3]} bài không có chữ, "
                f"{totals[4]} bài hết chữ đã gỡ chunk"
            )
        if totals[1] == 0 and totals[2]:
            print("Không có gì thay đổi nên không tốn quota nào.", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
