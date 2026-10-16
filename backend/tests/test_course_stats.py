"""The four numbers stored on `courses`, and every path that moves them.

`duration_total_s` is the one that had no path at all: the catalogue printed a
length only because the seed wrote one in by hand, so any course an instructor
built showed none. It is recounted from its rows -- never adjusted -- at each
place a video starts or stops counting, the same rule `rating_avg` follows.

`rebuild()` is the other half of that bargain: a counter that does drift can be
put back from the rows it summarises, which is what `scripts.rebuild_course_stats`
runs.
"""

import uuid
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Category,
    Course,
    CourseSection,
    Enrollment,
    Lesson,
    Review,
    User,
    VideoAsset,
)
from app.schemas.video import VideoUploadRequest
from app.services import course_stats
from app.services import curriculum as curriculum_service
from app.services import video as video_service
from app.workers import video as worker
from app.workers.video import TranscodeError, transcode


class FakeStorage:
    def presigned_put_url(
        self, key: str, content_type: str, expires_in: int, *, size_bytes: int
    ) -> str:
        return f"https://bucket.example/{key}"

    def download_file(self, key: str, destination: str) -> None:
        Path(destination).write_bytes(b"not really a video")

    def upload_file(self, source: str, key: str, content_type: str | None = None) -> None:
        pass

    def delete_prefix(self, prefix: str) -> None:
        pass


@pytest.fixture
def fake_ffmpeg(monkeypatch: pytest.MonkeyPatch) -> None:
    def _run(source: Path, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        manifest = output_dir / worker.MANIFEST_NAME
        manifest.write_text("#EXTM3U\n#EXT-X-ENDLIST\n", encoding="utf-8")
        return manifest

    monkeypatch.setattr(worker, "run_ffmpeg", _run)
    monkeypatch.setattr(worker, "probe_duration_seconds", lambda source: 754)


@dataclass
class Built:
    """One course, laid out so every path has something to take away."""

    instructor: User
    course: Course
    first_section: CourseSection
    second_section: CourseSection
    ten_minutes: Lesson  # ready, 600 s, first section
    five_minutes: Lesson  # ready, 300 s, first section
    processing: Lesson  # still transcoding, second section


async def _instructor(session: AsyncSession) -> User:
    user = User(
        email=f"gv-{uuid.uuid4().hex[:8]}@example.com",
        full_name="Giảng viên",
        password_hash="x",
        role="instructor",
    )
    session.add(user)
    await session.flush()
    return user


async def _course(session: AsyncSession, instructor: User) -> Course:
    category = Category(name="Lập trình", slug=f"lt-{uuid.uuid4().hex[:8]}")
    session.add(category)
    await session.flush()

    course = Course(
        instructor_id=instructor.id,
        category_id=category.id,
        title="Khóa thử",
        slug=f"khoa-thu-{uuid.uuid4().hex[:8]}",
        status="draft",
    )
    session.add(course)
    await session.flush()
    return course


async def _video_lesson(
    session: AsyncSession,
    section: CourseSection,
    position: int,
    *,
    status: str,
    duration_s: int | None,
) -> Lesson:
    asset_id = uuid.uuid4()
    asset = VideoAsset(
        id=asset_id,
        storage_key=f"videos/{asset_id}/original.mp4",
        status=status,
        duration_s=duration_s,
    )
    session.add(asset)
    await session.flush()

    lesson = Lesson(
        section_id=section.id,
        title=f"Video {position}",
        type="video",
        position=position,
        # The relationship, not just the column: the services read
        # `lesson.video_asset`, and on a row built here rather than loaded it
        # would otherwise be a lazy load -- IO outside the event loop.
        video_asset=asset,
    )
    session.add(lesson)
    await session.flush()
    return lesson


@pytest.fixture
async def built(db_session: AsyncSession) -> Built:
    instructor = await _instructor(db_session)
    course = await _course(db_session, instructor)

    first = CourseSection(course_id=course.id, title="Chương 1", position=0)
    second = CourseSection(course_id=course.id, title="Chương 2", position=1)
    db_session.add_all([first, second])
    await db_session.flush()

    ten = await _video_lesson(db_session, first, 0, status="ready", duration_s=600)
    five = await _video_lesson(db_session, first, 1, status="ready", duration_s=300)
    db_session.add(
        Lesson(
            section_id=first.id,
            title="Bài viết",
            type="article",
            position=2,
            article_content="Không có thời lượng.",
        )
    )
    processing = await _video_lesson(
        db_session, second, 0, status="processing", duration_s=None
    )
    # What the rows add up to, so a path that forgets to recount shows up as
    # a number that did not move -- rather than a 0 that was 0 all along.
    course.duration_total_s = 900
    await db_session.flush()

    return Built(instructor, course, first, second, ten, five, processing)


async def _fresh(session: AsyncSession, course_id: uuid.UUID) -> Course:
    """The row as the database has it now. `populate_existing` rather than
    `expire_all()`, which would also expire the fixtures' own objects and turn
    the next `built.course.id` into IO outside the event loop."""
    return await session.scalar(
        select(Course).where(Course.id == course_id).execution_options(populate_existing=True)
    )


async def _stored_duration(session: AsyncSession, course_id: uuid.UUID) -> int:
    # A column select always goes to the database; no expiry needed.
    return await session.scalar(
        select(Course.duration_total_s).where(Course.id == course_id)
    )


# --- The paths that move duration_total_s ----------------------------------


async def test_a_finished_transcode_counts_every_ready_video_of_its_course(
    db_session: AsyncSession, built: Built, fake_ffmpeg: None
) -> None:
    await transcode(db_session, FakeStorage(), built.processing.video_asset_id)

    assert await _stored_duration(db_session, built.course.id) == 600 + 300 + 754


async def test_a_failed_transcode_adds_nothing(
    db_session: AsyncSession, built: Built, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(source: Path, output_dir: Path) -> Path:
        raise TranscodeError("ffmpeg thất bại")

    monkeypatch.setattr(worker, "run_ffmpeg", _boom)

    await transcode(db_session, FakeStorage(), built.processing.video_asset_id)

    assert await _stored_duration(db_session, built.course.id) == 600 + 300


async def test_a_transcode_leaves_other_courses_alone(
    db_session: AsyncSession, built: Built, fake_ffmpeg: None
) -> None:
    other = await _course(db_session, built.instructor)
    other.duration_total_s = 42
    await db_session.flush()

    await transcode(db_session, FakeStorage(), built.processing.video_asset_id)

    assert await _stored_duration(db_session, other.id) == 42


async def test_replacing_a_video_takes_its_length_off_until_the_new_one_is_ready(
    db_session: AsyncSession, built: Built
) -> None:
    """The old asset row is deleted with the upload ticket; the new one has no
    length until the worker measures it."""
    await video_service.create_upload_ticket(
        db_session,
        built.ten_minutes.id,
        built.instructor,
        FakeStorage(),
        VideoUploadRequest(filename="moi.mp4", content_type="video/mp4", size_bytes=1024),
    )

    assert await _stored_duration(db_session, built.course.id) == 300


async def test_deleting_a_video_lesson_takes_its_length_off(
    db_session: AsyncSession, built: Built
) -> None:
    await curriculum_service.delete_lesson(db_session, built.five_minutes.id, built.instructor)

    assert await _stored_duration(db_session, built.course.id) == 600


async def test_deleting_a_section_takes_all_of_its_videos_off(
    db_session: AsyncSession, built: Built
) -> None:
    await curriculum_service.delete_section(
        db_session, built.first_section.id, built.instructor
    )

    assert await _stored_duration(db_session, built.course.id) == 0


async def test_a_recount_is_not_a_change_to_the_course(
    db_session: AsyncSession, built: Built, fake_ffmpeg: None
) -> None:
    """`updated_at` reads as "when did the instructor last edit this course" --
    a worker finishing in the background is not that."""
    before = await db_session.scalar(
        select(Course.updated_at).where(Course.id == built.course.id)
    )

    await transcode(db_session, FakeStorage(), built.processing.video_asset_id)

    after = await db_session.scalar(
        select(Course.updated_at).where(Course.id == built.course.id)
    )
    assert after == before


# --- rebuild(): putting drifted counters back ------------------------------


async def _learner(session: AsyncSession) -> User:
    user = User(
        email=f"hv-{uuid.uuid4().hex[:8]}@example.com",
        full_name="Học viên",
        password_hash="x",
        role="student",
    )
    session.add(user)
    await session.flush()
    return user


@pytest.fixture
async def drifted(db_session: AsyncSession, built: Built) -> Course:
    """Two students, ratings 5 and 4, 900 s of ready video -- and stored
    numbers that agree with none of it."""
    for rating in (5, 4):
        learner = await _learner(db_session)
        db_session.add(Enrollment(user_id=learner.id, course_id=built.course.id))
        db_session.add(Review(user_id=learner.id, course_id=built.course.id, rating=rating))
    await db_session.flush()

    built.course.students_count = 17
    built.course.rating_avg = Decimal("1.00")
    built.course.rating_count = 9
    built.course.duration_total_s = 5
    await db_session.flush()
    return built.course


async def test_rebuild_puts_every_counter_back_from_its_rows(
    db_session: AsyncSession, drifted: Course
) -> None:
    await course_stats.rebuild(db_session, [drifted.id])
    await db_session.commit()

    course = await _fresh(db_session, drifted.id)
    assert course.students_count == 2
    assert course.rating_avg == Decimal("4.50")
    assert course.rating_count == 2
    assert course.duration_total_s == 900


async def test_rebuild_reports_what_it_corrected(
    db_session: AsyncSession, drifted: Course
) -> None:
    """The report is the evidence that the numbers are reproducible: which
    course, which column, what was stored and what the rows say."""
    drifts = await course_stats.rebuild(db_session, [drifted.id])

    assert {(d.course_id, d.column, d.stored, d.actual) for d in drifts} == {
        (drifted.id, "students_count", 17, 2),
        (drifted.id, "rating_avg", Decimal("1.00"), Decimal("4.50")),
        (drifted.id, "rating_count", 9, 2),
        (drifted.id, "duration_total_s", 5, 900),
    }


async def test_a_second_rebuild_finds_nothing_to_correct(
    db_session: AsyncSession, drifted: Course
) -> None:
    await course_stats.rebuild(db_session, [drifted.id])
    await db_session.commit()

    assert await course_stats.rebuild(db_session, [drifted.id]) == []


async def test_a_dry_run_reports_without_writing(
    db_session: AsyncSession, drifted: Course
) -> None:
    drifts = await course_stats.rebuild(db_session, [drifted.id], dry_run=True)
    await db_session.commit()

    assert len(drifts) == 4
    course = await _fresh(db_session, drifted.id)
    assert course.students_count == 17
    assert course.duration_total_s == 5


async def test_a_course_with_no_rows_rebuilds_to_zero(
    db_session: AsyncSession, built: Built
) -> None:
    """No reviews is an average of 0, not NULL: the column is NOT NULL and the
    catalogue sorts on it."""
    empty = await _course(db_session, built.instructor)

    await course_stats.rebuild(db_session, [empty.id])
    await db_session.commit()

    course = await _fresh(db_session, empty.id)
    assert (course.students_count, course.rating_count, course.duration_total_s) == (0, 0, 0)
    assert course.rating_avg == Decimal("0.00")


# --- The script's report -----------------------------------------------------


def test_the_report_says_so_when_nothing_drifted() -> None:
    from scripts.rebuild_course_stats import format_report

    assert format_report([], 24, dry_run=False) == (
        "Đã kiểm 24 khóa học: mọi số liệu khớp với dữ liệu gốc."
    )


def test_the_report_names_each_corrected_number() -> None:
    from scripts.rebuild_course_stats import format_report

    course_id = uuid.uuid4()
    drifts = [
        course_stats.Drift(course_id, "python-co-ban", "duration_total_s", 0, 5400),
        course_stats.Drift(course_id, "python-co-ban", "students_count", 3, 2),
    ]

    report = format_report(drifts, 24, dry_run=True)

    assert report.splitlines() == [
        "Đã kiểm 24 khóa học, sẽ sửa 2 số liệu ở 1 khóa:",
        "  python-co-ban  duration_total_s: 0 -> 5400",
        "  python-co-ban  students_count: 3 -> 2",
        "Chạy thử (--dry-run): chưa ghi gì vào CSDL.",
    ]
