"""Give the seed courses' videos what their lecturer says in them.

    python -m scripts.seed_transcripts
    python -m scripts.seed_transcripts python-co-ban-cho-nguoi-moi-bat-dau

The seed videos are a sample HLS stream with nobody speaking in it, so the only
text the chatbot could search was a few short articles: four lessons on the
best course, which a top-6 search returns whole whatever the question. An
evaluation on that corpus measures the model and never the retrieval. These
transcripts are the lecture each video stands for, written for the seed.

Files live in `scripts/seed_data/transcripts/<course slug>/` and are named after
their lesson's place in the course, `<section>-<lesson>.srt|txt` counted from
0 -- the numbering of the seed's own video keys (`seed/<slug>/1-0.mp4`) -- so
renaming a lesson does not orphan its text.

Each goes through `services.transcripts.put_transcript`, the function behind
`PUT /lessons/{id}/transcript`, as the course's own instructor: read and
refused exactly as an upload from the UI would be, and kept in the bucket as
the original file. Run it inside a container on the dev stack, like
`ingest_course`: Windows cannot resolve the storage's host name.

A published course is then queued for ingest once, for the Celery worker, as
an upload from the UI would have it -- once per course, not once per file. A
draft course is ingested when it is published.
"""

import argparse
import asyncio
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select

from app.core.db import SessionLocal, engine
from app.core.exceptions import DomainError
from app.models import Course, CourseSection, Lesson, User
from app.schemas.video import TranscriptUpload
from app.services.storage import StorageNotConfiguredError, build_storage
from app.services.tasks import CeleryTaskQueue
from app.services.transcripts import put_transcript

TRANSCRIPTS = Path(__file__).parent / "seed_data" / "transcripts"

_NAME = re.compile(r"^(\d+)-(\d+)\.(srt|txt)$")


@dataclass(frozen=True, slots=True)
class TranscriptFile:
    section: int
    lesson: int
    path: Path


def transcript_files(folder: Path) -> list[TranscriptFile]:
    """The transcripts in one course's folder, in course order."""
    files = []
    for path in sorted(folder.iterdir()):
        match = _NAME.match(path.name)
        if match is None:
            raise SystemExit(f"Tên tệp phải có dạng <chương>-<bài>.srt|txt: {path}")
        files.append(TranscriptFile(int(match[1]), int(match[2]), path))
    return sorted(files, key=lambda file: (file.section, file.lesson))


class _IngestOnce:
    """A TaskQueue that notes which courses want ingesting.

    `put_transcript` queues an ingest for every file it stores. Eleven jobs
    for one course would each re-read the whole course, and run side by side.
    """

    def __init__(self) -> None:
        self.courses: list[uuid.UUID] = []

    def enqueue_transcode(self, video_asset_id: uuid.UUID) -> None:
        raise AssertionError("Gắn transcript không bao giờ phải transcode lại video")

    def enqueue_ingest(self, course_id: uuid.UUID) -> None:
        if course_id not in self.courses:
            self.courses.append(course_id)


async def seed_course(session, slug: str, storage, queue: _IngestOnce) -> None:
    course = await session.scalar(
        select(Course).where(Course.slug == slug, Course.deleted_at.is_(None))
    )
    if course is None:
        raise SystemExit(f"Không tìm thấy khóa học '{slug}'. Chạy scripts.seed trước.")
    instructor = await session.get(User, course.instructor_id)

    rows = await session.execute(
        select(CourseSection.position, Lesson)
        .join(Lesson, Lesson.section_id == CourseSection.id)
        .where(CourseSection.course_id == course.id)
    )
    lessons = {(section, lesson.position): lesson for section, lesson in rows}

    print(f"{slug} ({course.status}):")
    for file in transcript_files(TRANSCRIPTS / slug):
        lesson = lessons.get((file.section, file.lesson))
        if lesson is None:
            raise SystemExit(f"{file.path.name}: khóa học không có bài ở vị trí này")
        upload = TranscriptUpload(
            filename=file.path.name,
            # Bytes as they are, BOM included, like the file a browser reads.
            content=file.path.read_bytes().decode("utf-8"),
        )
        try:
            result = await put_transcript(session, lesson.id, instructor, storage, queue, upload)
        except DomainError as error:
            raise SystemExit(f"{file.path.name}: {error.message}") from None
        print(f"  {file.path.name:8} {result.characters:>5} ký tự  {lesson.title}")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "courses",
        nargs="*",
        help="Slug khóa học. Bỏ trống: mọi khóa có thư mục transcript.",
    )
    args = parser.parse_args()
    # The dev engine echoes every query to stdout, burying the file list.
    engine.echo = False
    slugs = args.courses or sorted(path.name for path in TRANSCRIPTS.iterdir() if path.is_dir())

    try:
        storage = build_storage()
    except StorageNotConfiguredError as error:
        raise SystemExit(error.message) from None

    queue = _IngestOnce()
    async with SessionLocal() as session:
        for slug in slugs:
            await seed_course(session, slug, storage, queue)

    for course_id in queue.courses:
        CeleryTaskQueue().enqueue_ingest(course_id)
    print(
        f"\nĐã xếp {len(queue.courses)} job ingest cho worker (khóa đang xuất bản)."
        if queue.courses
        else "\nKhông khóa nào đang xuất bản: transcript sẽ được nạp khi xuất bản."
    )


if __name__ == "__main__":
    asyncio.run(main())
