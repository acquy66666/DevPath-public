"""Recompute the numbers stored on every course from the rows they summarise.

    python -m scripts.rebuild_course_stats             # fix, and say what moved
    python -m scripts.rebuild_course_stats --dry-run   # only say it

`students_count`, `rating_avg`, `rating_count` and `duration_total_s` live on
`courses` so the catalogue can sort by them with an index. Every path that
changes their rows recounts them in the same transaction, but a path added
later that forgets to, or a row written by hand, leaves them wrong with nothing
to say so. This is what puts them back -- and, run against a healthy database,
what shows they were right: a report of zero corrections is the thesis's
evidence that the stored numbers are reproducible from the data.

It runs `course_stats.rebuild`, the same definitions the services recount with,
so "right" here cannot mean something different from "right" there.
"""

import argparse
import asyncio

from sqlalchemy import func, select

from app.core.db import SessionLocal
from app.models import Course
from app.services.course_stats import Drift, rebuild


def format_report(drifts: list[Drift], checked: int, *, dry_run: bool) -> str:
    """Plain text, one line per corrected number, for a terminal or a log."""
    if not drifts:
        return f"Đã kiểm {checked} khóa học: mọi số liệu khớp với dữ liệu gốc."

    verb = "sẽ sửa" if dry_run else "đã sửa"
    courses = len({drift.course_id for drift in drifts})
    lines = [f"Đã kiểm {checked} khóa học, {verb} {len(drifts)} số liệu ở {courses} khóa:"]
    lines += [
        f"  {drift.slug}  {drift.column}: {drift.stored} -> {drift.actual}"
        for drift in drifts
    ]
    if dry_run:
        lines.append("Chạy thử (--dry-run): chưa ghi gì vào CSDL.")
    return "\n".join(lines)


async def main(dry_run: bool) -> None:
    async with SessionLocal() as session:
        checked = await session.scalar(select(func.count()).select_from(Course))
        drifts = await rebuild(session, dry_run=dry_run)
        if not dry_run:
            await session.commit()

    print(format_report(drifts, checked, dry_run=dry_run))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dry-run", action="store_true", help="chỉ báo số liệu lệch, không ghi"
    )
    asyncio.run(main(parser.parse_args().dry_run))
