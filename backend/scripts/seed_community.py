"""Questions, answers, notes and reports around one course, so the screens that
show them are not empty.

    python -m scripts.seed_community
    python -m scripts.seed_community --purge

Q&A, the notification bell, a learner's notes and bookmarks, and the admin's
report queue all start empty on a fresh database, and none of them can be
filled by one click in front of an examiner: a question needs somebody to ask
it, an answer needs the instructor to sign in, a report needs a third person.
The evidence audit of 05/10/2026 found these were the screens no phase had
ever captured (`docs/report/assets/README.md`, section 3.2), for exactly that
reason. This writes a small, believable week of activity on "Python cơ bản cho
người mới bắt đầu":

- five questions from learners on five lessons, three answered by the course's
  instructor (the "giảng viên" badge), one answered only by another learner and
  one with only a spam reply, so the instructor's inbox has something under
  "chưa trả lời";
- votes, and one question its asker marked solved;
- the notifications those writes send -- `qa_question` to the instructor,
  `qa_reply` to each asker -- because they are sent by the services themselves;
- notes at video timestamps and two bookmarks for `hocvien07`, the learner the
  screenshots are taken as;
- two pending reports of the spam reply, from two different learners.

**It writes through the services** (`app/services/qa.py`, `study.py`,
`reports.py`), the same doors the API uses, like `scripts.seed_cart`: a plan
line that breaks a rule -- a learner not enrolled in the course, a vote on your
own question -- stops the script with the error the button would have shown.
**The one thing written directly is the clock**, as in `scripts.seed_sales`:
the services stamp rows with `now()`, and a week of questions all asked "vừa
xong" would not look like a week. Each thread, reply, resolve and the
notifications they sent are moved back to the hour the plan gives.

**Runs after `scripts.seed_interactions`**, whose learners do the asking (and
are enrolled in the course by its fixed random seed -- the test file checks the
plan against that population). Idempotent: a question already asked, a reply
already given, a note already written is skipped. `--purge` removes the
threads (their replies and votes go with them), every notification that points
at one of them -- including the instructor's, who outlives the seeded learners
-- the reports of their content, and the notes and bookmarks named below.
**Run it before `seed_interactions --purge`**: removing the learners first
would take their threads with them but leave the instructor's bell pointing at
questions that no longer exist.
"""

import argparse
import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.core.exceptions import DomainError
from app.models import (
    Bookmark,
    Course,
    CourseSection,
    Lesson,
    Note,
    Notification,
    QaReply,
    QaThread,
    QaVote,
    Report,
    User,
)
from app.services import qa as qa_service
from app.services import reports as reports_service
from app.services import study as study_service

COURSE_SLUG = "python-co-ban-cho-nguoi-moi-bat-dau"
INSTRUCTOR = "khoa.tran@devpath.example"

#: The learner the screenshots are taken as: enrolled in the course, owner of
#: the demo chat sessions, and the asker of a question the instructor answered.
SCREENSHOT_LEARNER = "hocvien07@seed.devpath.example"


def learner(number: int) -> str:
    return f"hocvien{number:02d}@seed.devpath.example"


@dataclass(frozen=True, slots=True)
class ReplyPlan:
    author: str
    body: str
    #: Minutes after the question was asked.
    after_minutes: int
    #: Learners who report this reply, each with the reason they pick.
    reported_by: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class ThreadPlan:
    lesson_title: str
    asker: str
    title: str
    body: str
    #: How long ago the question was asked.
    hours_ago: int
    replies: tuple[ReplyPlan, ...] = ()
    voters: tuple[str, ...] = ()
    #: Minutes after asking that the asker marked it solved; None leaves it open.
    resolved_after_minutes: int | None = None


@dataclass(frozen=True, slots=True)
class NotePlan:
    lesson_title: str
    timestamp_s: int
    content: str


@dataclass(frozen=True, slots=True)
class StudyPlan:
    email: str
    notes: tuple[NotePlan, ...] = ()
    bookmarks: tuple[str, ...] = field(default_factory=tuple)


THREADS: list[ThreadPlan] = [
    ThreadPlan(
        lesson_title="Vòng lặp for và range",
        asker=learner(25),
        title="Vì sao range(1, 10) không in ra số 10?",
        body=(
            "Em chạy `for i in range(1, 10): print(i)` thì chỉ ra từ 1 đến 9. "
            "Em tưởng phải ra cả số 10 chứ ạ?"
        ),
        hours_ago=74,
        replies=(
            ReplyPlan(
                author=INSTRUCTOR,
                body=(
                    "`range(start, stop)` dừng **trước** `stop`, nên `range(1, 10)` là "
                    "1…9. Muốn có 10 thì viết `range(1, 11)`.\n\n"
                    "Quy ước này để `range(n)` có đúng `n` phần tử và `range(a, b)` có "
                    "`b - a` phần tử — đếm nhẩm dễ hơn nhiều."
                ),
                after_minutes=95,
            ),
            ReplyPlan(
                author=learner(25),
                body="Dạ em hiểu rồi, cảm ơn thầy!",
                after_minutes=130,
            ),
        ),
        voters=(SCREENSHOT_LEARNER, learner(27), learner(31)),
        resolved_after_minutes=132,
    ),
    ThreadPlan(
        lesson_title="Ép kiểu và những cái bẫy quen thuộc",
        asker=SCREENSHOT_LEARNER,
        title='int("3.5") báo lỗi nhưng int(3.5) thì không?',
        body=(
            'Em thử `int("3.5")` thì bị `ValueError: invalid literal for int()`, '
            "mà `int(3.5)` lại ra 3. Sao hai cái khác nhau vậy ạ?"
        ),
        hours_ago=27,
        replies=(
            ReplyPlan(
                author=INSTRUCTOR,
                body=(
                    "`int()` nhận **chuỗi** thì chỉ chấp nhận chuỗi viết đúng một số "
                    'nguyên, nên `"3.5"` bị từ chối. Nhận **số thực** thì nó cắt bỏ '
                    "phần thập phân.\n\n"
                    'Muốn đổi chuỗi `"3.5"` thành 3 thì đi hai bước: '
                    '`int(float("3.5"))`.'
                ),
                after_minutes=210,
            ),
        ),
        voters=(learner(25), learner(29)),
    ),
    ThreadPlan(
        lesson_title="Bài tập: đếm số chẵn",
        asker=learner(28),
        title="Bài nộp bị quá thời gian ở test ẩn",
        body=(
            "Code của em qua hết test mẫu nhưng test ẩn cuối cùng báo “Quá thời "
            "gian”. Em dùng hai vòng lặp lồng nhau để đếm. Có cách nào nhanh hơn "
            "không ạ?"
        ),
        hours_ago=9,
        replies=(
            ReplyPlan(
                author=learner(32),
                body=(
                    "Mình cũng bị y vậy. Chỉ cần duyệt danh sách **một lần** và kiểm "
                    "`x % 2 == 0` là đủ, không cần vòng lặp lồng."
                ),
                after_minutes=40,
            ),
        ),
        voters=(learner(30),),
    ),
    ThreadPlan(
        lesson_title="Vòng lặp while và điều kiện dừng",
        asker=learner(32),
        title="Khi nào nên dùng while thay vì for?",
        body=(
            "Bài nào em cũng viết được bằng `for` thì `while` dùng vào lúc nào "
            "ạ? Có ví dụ nào mà `for` không làm được không?"
        ),
        hours_ago=5,
        replies=(
            ReplyPlan(
                author=learner(36),
                body="Tài liệu Python giá rẻ, inbox mình để nhận link tải trọn bộ nhé!!!",
                after_minutes=12,
                reported_by=(
                    (learner(32), "spam"),
                    (SCREENSHOT_LEARNER, "spam"),
                ),
            ),
        ),
    ),
    ThreadPlan(
        lesson_title="f-string: ghép chuỗi cho người đọc",
        asker=learner(29),
        title="f-string làm tròn số thế nào?",
        body="Em muốn in `3.14159` thành `3.14` trong f-string thì viết sao ạ?",
        hours_ago=50,
        replies=(
            ReplyPlan(
                author=INSTRUCTOR,
                body=(
                    'Thêm định dạng sau dấu hai chấm: `f"{pi:.2f}"` → `3.14`. '
                    "`.2f` nghĩa là số thực, giữ 2 chữ số sau dấu chấm."
                ),
                after_minutes=60,
            ),
        ),
        voters=(learner(28),),
    ),
]

STUDY: list[StudyPlan] = [
    StudyPlan(
        email=SCREENSHOT_LEARNER,
        # Plain text: notes are shown as written, not rendered as Markdown.
        notes=(
            NotePlan(
                "Vòng lặp for và range",
                85,
                "range(start, stop, step) dừng TRƯỚC stop: range(1, 10) là 1 đến 9.",
            ),
            NotePlan(
                "Vòng lặp for và range",
                192,
                "Duyệt list bằng for x in ds thay vì for i in range(len(ds)).",
            ),
            NotePlan(
                "Biến và phép gán",
                40,
                'Không cần khai báo kiểu: x = 5 rồi x = "năm" vẫn chạy.',
            ),
        ),
        bookmarks=("Vòng lặp for và range", "Ép kiểu và những cái bẫy quen thuộc"),
    ),
]


@dataclass(frozen=True, slots=True)
class Written:
    threads: int
    replies: int
    votes: int
    notes: int
    bookmarks: int
    reports: int


@dataclass(frozen=True, slots=True)
class Purged:
    threads: int
    notifications: int
    reports: int
    notes: int
    bookmarks: int


def _people(threads: list[ThreadPlan], study: list[StudyPlan]) -> set[str]:
    emails = {INSTRUCTOR}
    for thread in threads:
        emails |= {thread.asker, *thread.voters}
        for reply in thread.replies:
            emails |= {reply.author, *(email for email, _ in reply.reported_by)}
    emails |= {plan.email for plan in study}
    return emails


def _lesson_titles(threads: list[ThreadPlan], study: list[StudyPlan]) -> set[str]:
    titles = {thread.lesson_title for thread in threads}
    for plan in study:
        titles |= {note.lesson_title for note in plan.notes} | set(plan.bookmarks)
    return titles


async def _users(session: AsyncSession, emails: set[str]) -> dict[str, User]:
    return {
        user.email: user
        for user in await session.scalars(select(User).where(User.email.in_(emails)))
    }


async def _lessons(session: AsyncSession, titles: set[str]) -> dict[str, Lesson]:
    return {
        lesson.title: lesson
        for lesson in await session.scalars(
            select(Lesson)
            .join(CourseSection, CourseSection.id == Lesson.section_id)
            .join(Course, Course.id == CourseSection.course_id)
            .where(Course.slug == COURSE_SLUG, Lesson.title.in_(titles))
        )
    }


async def _load(
    session: AsyncSession, threads: list[ThreadPlan], study: list[StudyPlan]
) -> tuple[dict[str, User], dict[str, Lesson]]:
    emails = _people(threads, study)
    users = await _users(session, emails)
    missing_users = sorted(emails - set(users))
    if missing_users:
        raise SystemExit(
            "Chưa có các tài khoản: "
            + ", ".join(missing_users)
            + ". Chạy `python -m scripts.seed` và `python -m scripts.seed_interactions` trước."
        )

    titles = _lesson_titles(threads, study)
    lessons = await _lessons(session, titles)
    missing_lessons = sorted(titles - set(lessons))
    if missing_lessons:
        raise SystemExit(
            f"Khóa {COURSE_SLUG} chưa có các bài: "
            + ", ".join(missing_lessons)
            + ". Chạy `python -m scripts.seed` trước."
        )
    return users, lessons


def _stop(what: str, refusal: DomainError) -> SystemExit:
    return SystemExit(
        f"{what}: {refusal.message} ({refusal.code}). Sửa kế hoạch trong scripts/seed_community.py."
    )


async def _backdate_thread(session: AsyncSession, thread_id: uuid.UUID, at: datetime) -> None:
    await session.execute(
        update(QaThread).where(QaThread.id == thread_id).values(created_at=at, updated_at=at)
    )
    # The instructor's `qa_question` about it.
    await session.execute(
        update(Notification)
        .where(
            Notification.type == "qa_question",
            Notification.payload["thread_id"].astext == str(thread_id),
        )
        .values(created_at=at, updated_at=at)
    )


async def _backdate_reply(session: AsyncSession, reply_id: uuid.UUID, at: datetime) -> None:
    await session.execute(
        update(QaReply).where(QaReply.id == reply_id).values(created_at=at, updated_at=at)
    )
    # The asker's `qa_reply` about it.
    await session.execute(
        update(Notification)
        .where(
            Notification.type == "qa_reply",
            Notification.payload["reply_id"].astext == str(reply_id),
        )
        .values(created_at=at, updated_at=at)
    )


async def seed_community(
    session: AsyncSession,
    threads: list[ThreadPlan] = THREADS,
    study: list[StudyPlan] = STUDY,
    *,
    now: datetime | None = None,
) -> Written:
    """Ask, answer, vote, report, take notes -- skipping whatever already exists."""
    users, lessons = await _load(session, threads, study)
    now = now or datetime.now(UTC)
    counts = dict(threads=0, replies=0, votes=0, notes=0, bookmarks=0, reports=0)

    for plan in threads:
        asker = users[plan.asker]
        lesson = lessons[plan.lesson_title]
        asked_at = now - timedelta(hours=plan.hours_ago)

        thread_id = await session.scalar(
            select(QaThread.id).where(
                QaThread.lesson_id == lesson.id,
                QaThread.user_id == asker.id,
                QaThread.title == plan.title,
            )
        )
        if thread_id is None:
            try:
                view = await qa_service.create_thread(
                    session, lesson.id, asker, title=plan.title, body=plan.body
                )
            except DomainError as refusal:
                raise _stop(
                    f"{plan.asker} không hỏi được ở bài {plan.lesson_title}", refusal
                ) from refusal
            thread_id = view.thread.id
            await _backdate_thread(session, thread_id, asked_at)
            counts["threads"] += 1

        for reply in plan.replies:
            author = users[reply.author]
            reply_id = await session.scalar(
                select(QaReply.id).where(
                    QaReply.thread_id == thread_id,
                    QaReply.user_id == author.id,
                    QaReply.body == reply.body,
                )
            )
            if reply_id is None:
                try:
                    written = await qa_service.create_reply(
                        session, thread_id, author, body=reply.body
                    )
                except DomainError as refusal:
                    raise _stop(
                        f"{reply.author} không trả lời được «{plan.title}»", refusal
                    ) from refusal
                reply_id = written.id
                await _backdate_reply(
                    session, reply_id, asked_at + timedelta(minutes=reply.after_minutes)
                )
                counts["replies"] += 1

            for reporter_email, reason in reply.reported_by:
                reporter = users[reporter_email]
                present = await session.scalar(
                    select(Report.id).where(
                        Report.reporter_id == reporter.id,
                        Report.target_type == "qa_reply",
                        Report.target_id == reply_id,
                    )
                )
                if present is not None:
                    continue
                try:
                    await reports_service.create(
                        session,
                        reporter,
                        target_type="qa_reply",
                        target_id=reply_id,
                        reason=reason,
                        details=None,
                    )
                except DomainError as refusal:
                    raise _stop(f"{reporter_email} không báo cáo được", refusal) from refusal
                counts["reports"] += 1

        for voter_email in plan.voters:
            voter = users[voter_email]
            present = await session.scalar(
                select(QaVote.id).where(QaVote.thread_id == thread_id, QaVote.user_id == voter.id)
            )
            if present is not None:
                continue
            try:
                await qa_service.vote(session, thread_id, voter)
            except DomainError as refusal:
                raise _stop(
                    f"{voter_email} không bình chọn được «{plan.title}»", refusal
                ) from refusal
            counts["votes"] += 1

        if plan.resolved_after_minutes is not None:
            resolved_at = asked_at + timedelta(minutes=plan.resolved_after_minutes)
            current = await session.scalar(
                select(QaThread.resolved_at).where(QaThread.id == thread_id)
            )
            if current is None:
                await qa_service.update_thread(session, thread_id, asker, resolved=True)
                await session.execute(
                    update(QaThread)
                    .where(QaThread.id == thread_id)
                    .values(resolved_at=resolved_at, updated_at=resolved_at)
                )

    for plan in study:
        owner = users[plan.email]
        for note in plan.notes:
            lesson = lessons[note.lesson_title]
            present = await session.scalar(
                select(Note.id).where(
                    Note.user_id == owner.id,
                    Note.lesson_id == lesson.id,
                    Note.timestamp_s == note.timestamp_s,
                    Note.content == note.content,
                )
            )
            if present is not None:
                continue
            try:
                await study_service.create_note(
                    session,
                    lesson.id,
                    owner,
                    timestamp_s=note.timestamp_s,
                    content=note.content,
                )
            except DomainError as refusal:
                raise _stop(
                    f"{plan.email} không ghi chú được ở {note.lesson_title}", refusal
                ) from refusal
            counts["notes"] += 1

        for title in plan.bookmarks:
            lesson = lessons[title]
            present = await session.scalar(
                select(Bookmark.id).where(
                    Bookmark.user_id == owner.id, Bookmark.lesson_id == lesson.id
                )
            )
            if present is not None:
                continue
            await study_service.add_bookmark(session, lesson.id, owner)
            counts["bookmarks"] += 1

    await session.flush()
    return Written(**counts)


async def purge(
    session: AsyncSession,
    threads: list[ThreadPlan] = THREADS,
    study: list[StudyPlan] = STUDY,
) -> Purged:
    """Take back exactly what the plan names, and what it caused.

    A thread is this script's when its lesson, asker and title match a plan
    line. Its replies and votes go with it (ON DELETE CASCADE); the
    notifications and reports pointing at it do not -- they reference it by id
    inside a payload or a polymorphic column -- so they are deleted here first.
    """
    users = await _users(session, _people(threads, study))
    lessons = await _lessons(session, _lesson_titles(threads, study))

    thread_ids: list[uuid.UUID] = []
    for plan in threads:
        asker = users.get(plan.asker)
        lesson = lessons.get(plan.lesson_title)
        if asker is None or lesson is None:
            continue
        thread_id = await session.scalar(
            select(QaThread.id).where(
                QaThread.lesson_id == lesson.id,
                QaThread.user_id == asker.id,
                QaThread.title == plan.title,
            )
        )
        if thread_id is not None:
            thread_ids.append(thread_id)

    notifications = reports = 0
    if thread_ids:
        reply_ids = list(
            await session.scalars(select(QaReply.id).where(QaReply.thread_id.in_(thread_ids)))
        )
        result = await session.execute(
            delete(Notification).where(
                Notification.type.in_(("qa_question", "qa_reply")),
                Notification.payload["thread_id"].astext.in_([str(i) for i in thread_ids]),
            )
        )
        notifications = result.rowcount or 0
        result = await session.execute(
            delete(Report).where(
                Report.target_id.in_([*thread_ids, *reply_ids]),
                Report.target_type.in_(("qa_thread", "qa_reply")),
            )
        )
        reports = result.rowcount or 0
        await session.execute(delete(QaThread).where(QaThread.id.in_(thread_ids)))

    notes = bookmarks = 0
    for plan in study:
        owner = users.get(plan.email)
        if owner is None:
            continue
        for note in plan.notes:
            lesson = lessons.get(note.lesson_title)
            if lesson is None:
                continue
            result = await session.execute(
                delete(Note).where(
                    Note.user_id == owner.id,
                    Note.lesson_id == lesson.id,
                    Note.timestamp_s == note.timestamp_s,
                    Note.content == note.content,
                )
            )
            notes += result.rowcount or 0
        marked = [lessons[title].id for title in plan.bookmarks if title in lessons]
        if marked:
            result = await session.execute(
                delete(Bookmark).where(Bookmark.user_id == owner.id, Bookmark.lesson_id.in_(marked))
            )
            bookmarks += result.rowcount or 0

    await session.flush()
    return Purged(
        threads=len(thread_ids),
        notifications=notifications,
        reports=reports,
        notes=notes,
        bookmarks=bookmarks,
    )


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--purge",
        action="store_true",
        help=(
            "Xóa đúng các câu hỏi, ghi chú, đánh dấu, báo cáo script này tạo, "
            "cùng các thông báo trỏ vào chúng."
        ),
    )
    args = parser.parse_args()

    async with SessionLocal() as session:
        if args.purge:
            purged = await purge(session)
            await session.commit()
            print(
                f"Đã xóa {purged.threads} câu hỏi (kèm trả lời và bình chọn), "
                f"{purged.notifications} thông báo, {purged.reports} báo cáo, "
                f"{purged.notes} ghi chú, {purged.bookmarks} đánh dấu."
            )
            return

        written = await seed_community(session)
        await session.commit()

    print(f"câu hỏi    : {written.threads} tạo mới")
    print(f"trả lời    : {written.replies} tạo mới")
    print(f"bình chọn  : {written.votes} tạo mới")
    print(f"báo cáo    : {written.reports} tạo mới")
    print(f"ghi chú    : {written.notes} tạo mới")
    print(f"đánh dấu   : {written.bookmarks} tạo mới")
    print(
        f"\nXem bằng {SCREENSHOT_LEARNER} (mật khẩu học viên seed) ở trang học "
        f"/hoc/{COURSE_SLUG}, và {INSTRUCTOR} ở /giang-day/hoi-dap."
    )


if __name__ == "__main__":
    asyncio.run(main())
