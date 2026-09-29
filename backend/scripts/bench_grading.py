"""How long grading takes, and how much of it a queue can absorb at once.

The number a student feels is not the time the sandbox spends running their
code. It is the time between pressing "Nộp bài" and seeing a verdict, and on a
loaded queue most of that is waiting for a worker slot. So this script measures
the whole path -- API, Celery, worker, container, database -- and splits the
result into the two halves that have different fixes:

    chờ hàng đợi   submit -> worker picks it up      fixed by more workers
    chấm           worker starts -> verdict written   fixed by faster sandbox

Both come from the live progress channel rather than from the script's own
guesses: the worker publishes `running` before the first case and one event per
case, so subscribing to Redis gives a timestamp for each boundary without
adding a column to the database or a stopwatch to the worker.

It runs against a real stack -- real Redis, real Celery, real Docker sandbox --
because the thing being measured is the container start, and a fake would
measure nothing. Everything it creates (a course, an exercise, its cases and
one student per submission) is deleted afterwards unless `--keep` says not to.

    docker compose exec backend python -m scripts.bench_grading
    docker compose exec backend python -m scripts.bench_grading --submissions 20 --cases 8

One student per submission on purpose: ten submissions from one account is not
a load test, it is a rate-limit test, and the limiter would refuse nine of them
(`submission_cooldown_seconds`). Ten students submitting at once is also the
scenario the plan asks about -- a class hitting the same exercise in a lab.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

import httpx
import redis.asyncio as aioredis
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models import (
    Category,
    CodeExercise,
    Course,
    CourseSection,
    Enrollment,
    Lesson,
    Submission,
    SubmissionResult,
    TestCase,
    User,
)
from app.services import certificates

API = "http://localhost:8000"
PASSWORD = "bench-mat-khau-du-dai"

#: A correct solution that does nothing clever. The point of the measurement is
#: the machinery around the program, so the program has to be small enough that
#: its own runtime is not what is being reported.
SOLUTION = "a, b = input().split()\nprint(int(a) + int(b))\n"

#: Where the worker publishes progress. Same string as `grading_events.CHANNEL`
#: with the submission id left as a pattern.
CHANNEL_PATTERN = "grading:events:*"

#: Long enough for a slow first container pull, short enough that a broken
#: worker fails the run instead of hanging a terminal all afternoon.
DEADLINE_SECONDS = 300.0


@dataclass
class Timeline:
    """When each boundary was crossed, on the clock of the machine measuring."""

    submitted_at: float
    running_at: float | None = None
    finished_at: float | None = None
    status: str | None = None
    verdict: str | None = None
    #: `run_time_ms` per case, as the sandbox measured it from inside.
    case_ms: list[int] = field(default_factory=list)

    @property
    def waited(self) -> float | None:
        if self.running_at is None:
            return None
        return self.running_at - self.submitted_at

    @property
    def graded(self) -> float | None:
        if self.running_at is None or self.finished_at is None:
            return None
        return self.finished_at - self.running_at

    @property
    def total(self) -> float | None:
        if self.finished_at is None:
            return None
        return self.finished_at - self.submitted_at


@dataclass
class Fixture:
    """The throwaway world one run happens in."""

    category_id: uuid.UUID
    course_id: uuid.UUID
    exercise_id: uuid.UUID
    student_ids: list[uuid.UUID]
    student_emails: list[str]


async def build_fixture(students: int, cases: int, tag: str) -> Fixture:
    """A published course with one exercise, and one enrolled student each."""
    async with SessionLocal() as session:
        category = Category(name=f"Benchmark {tag}", slug=f"benchmark-{tag}")
        instructor = User(
            email=f"bench.gv.{tag}@devpath.example",
            full_name="Benchmark instructor",
            password_hash=hash_password(PASSWORD),
            role="instructor",
        )
        session.add_all([category, instructor])
        await session.flush()

        course = Course(
            instructor_id=instructor.id,
            category_id=category.id,
            title=f"Benchmark chấm bài {tag}",
            slug=f"benchmark-cham-bai-{tag}",
            price=Decimal("0"),
            status="published",
            published_at=datetime.now(UTC),
        )
        session.add(course)
        await session.flush()

        section = CourseSection(course_id=course.id, title="Chương 1", position=0)
        session.add(section)
        await session.flush()

        lesson = Lesson(
            section_id=section.id,
            title="Tổng hai số",
            type="code_exercise",
            position=0,
        )
        session.add(lesson)
        await session.flush()

        exercise = CodeExercise(
            lesson_id=lesson.id,
            statement_md="Đọc hai số, in ra tổng.",
            starter_code=SOLUTION,
            language="python",
            time_limit_ms=2000,
            memory_limit_mb=128,
        )
        session.add(exercise)
        await session.flush()

        # Half the cases visible, half hidden -- the mix an exercise actually
        # has, and the worker runs both the same way.
        session.add_all(
            TestCase(
                exercise_id=exercise.id,
                position=index,
                input=f"{index} {index + 1}",
                expected_output=f"{index * 2 + 1}\n",
                is_hidden=index >= cases // 2,
                score_weight=1,
            )
            for index in range(cases)
        )

        # One extra: the warm-up runs alone and must not spend a cooldown that
        # belongs to a student in the burst.
        people = []
        for index in range(students + 1):
            student = User(
                email=f"bench.hv{index}.{tag}@devpath.example",
                full_name=f"Benchmark student {index}",
                password_hash=hash_password(PASSWORD),
                role="student",
            )
            session.add(student)
            people.append(student)
        await session.flush()

        session.add_all(
            Enrollment(user_id=student.id, course_id=course.id) for student in people
        )
        await session.commit()

        return Fixture(
            category_id=category.id,
            course_id=course.id,
            exercise_id=exercise.id,
            student_ids=[student.id for student in people],
            student_emails=[student.email for student in people],
        )


async def tear_down(fixture: Fixture, tag: str) -> None:
    """Remove everything the run created, in an order the keys allow."""
    async with SessionLocal() as session:
        submissions = (
            await session.execute(
                select(Submission.id).where(Submission.exercise_id == fixture.exercise_id)
            )
        ).scalars().all()
        if submissions:
            await session.execute(
                delete(SubmissionResult).where(
                    SubmissionResult.submission_id.in_(submissions)
                )
            )
            await session.execute(
                delete(Submission).where(Submission.id.in_(submissions))
            )
        await session.execute(
            delete(TestCase).where(TestCase.exercise_id == fixture.exercise_id)
        )
        await session.execute(
            delete(CodeExercise).where(CodeExercise.id == fixture.exercise_id)
        )
        lessons = (
            await session.execute(
                select(Lesson.id)
                .join(CourseSection, CourseSection.id == Lesson.section_id)
                .where(CourseSection.course_id == fixture.course_id)
            )
        ).scalars().all()
        if lessons:
            await session.execute(delete(Lesson).where(Lesson.id.in_(lessons)))
        await session.execute(
            delete(CourseSection).where(CourseSection.course_id == fixture.course_id)
        )
        # An accepted run finishes the one-lesson course and issues a
        # certificate, which holds on to the enrolment (RESTRICT).
        await certificates.delete_for_enrollments(
            session, select(Enrollment.id).where(Enrollment.course_id == fixture.course_id)
        )
        await session.execute(
            delete(Enrollment).where(Enrollment.course_id == fixture.course_id)
        )
        await session.execute(delete(Course).where(Course.id == fixture.course_id))
        await session.execute(
            delete(User).where(User.email.like(f"bench.%.{tag}@devpath.example"))
        )
        await session.execute(delete(Category).where(Category.id == fixture.category_id))
        await session.commit()


async def worker_pool() -> str:
    """How many submissions the queue can actually grade at once.

    Asked of the running workers rather than read from a setting: the number
    that matters is the one Celery started with, and a stale env var in this
    container would put a wrong denominator on every throughput figure in the
    report.
    """

    def probe() -> str:
        from app.workers.celery_app import celery_app

        inspector = celery_app.control.inspect(timeout=3.0)
        queues = inspector.active_queues() or {}
        stats = inspector.stats() or {}
        graders = [
            name
            for name, subscribed in queues.items()
            if any(queue["name"] == "grading" for queue in subscribed)
        ]
        if not graders:
            return "không hỏi được worker nào"
        slots = sum(
            stats.get(name, {}).get("pool", {}).get("max-concurrency", 0)
            for name in graders
        )
        return f"{slots} slot ({len(graders)} worker)"

    return await asyncio.to_thread(probe)


async def sign_in(client: httpx.AsyncClient, email: str) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
    )
    response.raise_for_status()
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


class Listener:
    """The progress channel, read for its timestamps rather than its contents.

    Subscribed before the first submission is sent: Redis pub/sub has no
    replay, so a subscription opened afterwards would miss exactly the `running`
    event this script exists to time.
    """

    def __init__(self) -> None:
        self._redis = aioredis.from_url(get_settings().redis_url)
        self._task: asyncio.Task | None = None
        self.timelines: dict[str, Timeline] = {}

    async def start(self) -> None:
        self._pubsub = self._redis.pubsub()
        await self._pubsub.psubscribe(CHANNEL_PATTERN)
        self._task = asyncio.create_task(self._read())

    async def _read(self) -> None:
        async for message in self._pubsub.listen():
            if message["type"] != "pmessage":
                continue
            now = time.monotonic()
            event = json.loads(message["data"])
            timeline = self.timelines.get(event["submission_id"])
            if timeline is None:
                continue  # Somebody else's submission; not part of this run.
            if event["status"] == "running" and timeline.running_at is None:
                timeline.running_at = now
            if event.get("case") is not None:
                run_time = event["case"].get("run_time_ms")
                if run_time is not None:
                    timeline.case_ms.append(run_time)
            if event["status"] in {"done", "error"}:
                timeline.finished_at = now
                timeline.status = event["status"]
                timeline.verdict = event.get("verdict")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
        await self._pubsub.punsubscribe(CHANNEL_PATTERN)
        await self._pubsub.aclose()
        await self._redis.aclose()


async def await_completion(listener: Listener, expected: int) -> bool:
    """Wait until every submission has reported a terminal status."""
    deadline = time.monotonic() + DEADLINE_SECONDS
    while time.monotonic() < deadline:
        done = sum(1 for t in listener.timelines.values() if t.finished_at is not None)
        if done >= expected:
            return True
        await asyncio.sleep(0.05)
    return False


async def fire(
    client: httpx.AsyncClient,
    listener: Listener,
    exercise_id: uuid.UUID,
    headers: dict[str, str],
) -> None:
    response = await client.post(
        f"/api/v1/code-exercises/{exercise_id}/submissions",
        json={"code": SOLUTION},
        headers=headers,
    )
    response.raise_for_status()
    listener.timelines[response.json()["id"]] = Timeline(submitted_at=time.monotonic())


def describe(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    return {
        "n": len(ordered),
        "mean": statistics.fmean(ordered),
        "p50": statistics.median(ordered),
        "p90": ordered[max(0, round(0.9 * len(ordered)) - 1)],
        "max": ordered[-1],
    }


def seconds(value: float) -> str:
    return f"{value:.2f}s"


def report(
    burst: list[Timeline],
    warmup: Timeline | None,
    cases: int,
    concurrency: str,
) -> dict:
    """Print the run as markdown, and hand the raw numbers back."""
    graded = [t for t in burst if t.finished_at is not None]
    broken = [t for t in burst if t.status == "error" or t.finished_at is None]

    first_submit = min(t.submitted_at for t in burst)
    last_finish = max(t.finished_at for t in graded)
    span = last_finish - first_submit

    totals = describe([t.total for t in graded])
    waits = describe([t.waited for t in graded if t.waited is not None])
    grades = describe([t.graded for t in graded if t.graded is not None])
    sandbox_ms = [ms for t in graded for ms in t.case_ms]

    print()
    print(f"### Burst: {len(burst)} bài nộp cùng lúc, {cases} test case mỗi bài")
    print()
    print(f"- Worker concurrency: **{concurrency}**")
    failures = f" (lỗi: {len(broken)})" if broken else ""
    print(f"- Hoàn tất: **{len(graded)}/{len(burst)}**{failures}")
    print(f"- Toàn bộ đợt xong trong **{seconds(span)}**")
    print(
        f"- Throughput: **{len(graded) / span * 60:.1f} bài/phút** "
        f"· **{len(graded) * cases / span:.1f} test case/giây**"
    )
    print()
    print("| Đo | Trung bình | p50 | p90 | Chậm nhất |")
    print("|---|---|---|---|---|")
    for label, stats in (
        ("Tổng (nộp → verdict)", totals),
        ("Chờ hàng đợi", waits),
        ("Chấm (worker chạy)", grades),
    ):
        print(
            f"| {label} | {seconds(stats['mean'])} | {seconds(stats['p50'])} "
            f"| {seconds(stats['p90'])} | {seconds(stats['max'])} |"
        )
    print()
    if sandbox_ms:
        inside = statistics.fmean(sandbox_ms) / 1000
        per_case = statistics.fmean([t.graded for t in graded]) / cases
        print(
            f"- Một test case: **{per_case * 1000:.0f} ms** tính cả dựng container, "
            f"trong đó **{inside * 1000:.0f} ms** là chương trình chạy bên trong "
            f"→ chi phí sandbox **{(per_case - inside) * 1000:.0f} ms/case**"
        )
    if warmup is not None and warmup.total is not None:
        print(
            f"- Một mình một hàng đợi: **{seconds(warmup.total)}** "
            f"(chờ {seconds(warmup.waited or 0)} + chấm {seconds(warmup.graded or 0)})"
        )
    print()

    return {
        "cases_per_submission": cases,
        "concurrency": concurrency,
        "submissions": len(burst),
        "completed": len(graded),
        "failed": len(broken),
        "span_seconds": span,
        "throughput_per_minute": len(graded) / span * 60,
        "total": totals,
        "wait": waits,
        "grade": grades,
        "sandbox_case_ms_mean": statistics.fmean(sandbox_ms) if sandbox_ms else None,
        "warmup_total_seconds": warmup.total if warmup else None,
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--submissions", type=int, default=10)
    parser.add_argument("--cases", type=int, default=5)
    parser.add_argument(
        "--keep",
        action="store_true",
        help="giữ lại khóa học và tài khoản đã tạo, để xem bằng mắt",
    )
    parser.add_argument("--json", dest="json_path", default=None)
    parser.add_argument(
        "--no-warmup",
        action="store_true",
        help="bỏ lần chạy khởi động; số đo đợt đầu sẽ gánh cả chi phí kéo image",
    )
    args = parser.parse_args()

    tag = uuid.uuid4().hex[:6]
    print(f"Chuẩn bị dữ liệu (tag {tag})…")
    fixture = await build_fixture(args.submissions, args.cases, tag)

    listener = Listener()
    await listener.start()
    try:
        async with httpx.AsyncClient(base_url=API, timeout=60) as client:
            tokens = await asyncio.gather(
                *(sign_in(client, email) for email in fixture.student_emails)
            )

            warmup: Timeline | None = None
            if not args.no_warmup:
                print("Chạy khởi động một bài (làm nóng image, cache, kết nối)…")
                await fire(client, listener, fixture.exercise_id, tokens[-1])
                if not await await_completion(listener, 1):
                    raise SystemExit("bài khởi động không kết thúc — worker có chạy không?")
                warmup = next(iter(listener.timelines.values()))
                listener.timelines.clear()

            print(f"Bắn {args.submissions} bài nộp cùng lúc…")
            await asyncio.gather(
                *(
                    fire(client, listener, fixture.exercise_id, tokens[index])
                    for index in range(args.submissions)
                )
            )
            finished = await await_completion(listener, args.submissions)

        burst = list(listener.timelines.values())
        if not finished:
            print(
                f"CẢNH BÁO: hết {DEADLINE_SECONDS:.0f}s mà mới xong "
                f"{sum(1 for t in burst if t.finished_at)}/{len(burst)} bài."
            )
        numbers = report(burst, warmup, args.cases, await worker_pool())
        if args.json_path:
            with open(args.json_path, "w", encoding="utf-8") as handle:
                json.dump(numbers, handle, ensure_ascii=False, indent=2)
            print(f"Số liệu thô: {args.json_path}")
    finally:
        await listener.stop()
        if args.keep:
            print(f"Giữ lại dữ liệu: khóa học benchmark-cham-bai-{tag}")
        else:
            await tear_down(fixture, tag)
            print("Đã xóa dữ liệu benchmark.")


if __name__ == "__main__":
    asyncio.run(main())
